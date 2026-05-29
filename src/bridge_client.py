"""Thin client for the local Copilot bridge (chat completions, OpenAI-compatible)."""
from __future__ import annotations
import json
import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from .config import BRIDGE_API_KEY, BRIDGE_BASE_URL, BRIDGE_MODEL


def _is_retryable(exc: BaseException) -> bool:
    """Retry only transient failures: timeouts, connection drops, and 5xx.

    A 4xx (bad request, auth, model-not-found) will never succeed on retry, so
    we surface it immediately instead of burning the retry budget.
    """
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    response_format_json: bool = False,
    timeout: float = 120.0,
) -> str:
    """Send a chat request and return the assistant message content."""
    body: dict = {
        "model": model or BRIDGE_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        f"{BRIDGE_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {BRIDGE_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body),
        timeout=timeout,
    )
    r.raise_for_status()
    payload = r.json()
    return payload["choices"][0]["message"]["content"]


def ask_json(system: str, user: str) -> dict:
    """Ask the model for a strict JSON object response, then parse."""
    raw = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format_json=False,
    )
    text = raw.strip()
    # Strip code fences if present
    if text.startswith("```"):
        text = text.split("```", 2)[-1]
        if text.lstrip().lower().startswith("json"):
            text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.split("```", 1)[0]
    return json.loads(text)

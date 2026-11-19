"""Thin wrapper around an OpenAI-compatible chat endpoint.

Works with OpenAI, Ollama (http://localhost:11434/v1), Groq, LM Studio, etc.
"""
from __future__ import annotations

from openai import OpenAI

from . import config

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # api_key must be non-empty even for local servers; Ollama accepts any value.
        _client = OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY or "not-needed",
        )
    return _client


_no_temperature: set[str] = set()  # models that rejected a custom temperature


def _rejects_temperature(exc: Exception) -> bool:
    """Newer reasoning-style models only accept the default temperature and answer 400 otherwise."""
    return getattr(exc, "status_code", None) == 400 and "temperature" in str(exc).lower()


def chat(system_prompt: str, user_prompt: str, temperature: float = 0.1, model: str | None = None) -> str:
    """Send a single-turn chat request and return the assistant's text.

    `model` overrides LLM_MODEL (used for a separate judge model). If the model refuses a custom
    temperature, the call is retried without it and remembered for the rest of the process.
    """
    client = _get_client()
    model = model or config.LLM_MODEL
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if model not in _no_temperature:
        kwargs["temperature"] = temperature
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        if "temperature" not in kwargs or not _rejects_temperature(exc):
            raise
        _no_temperature.add(model)
        kwargs.pop("temperature")
        response = client.chat.completions.create(**kwargs)
    return (response.choices[0].message.content or "").strip()

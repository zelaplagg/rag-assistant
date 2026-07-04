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


def chat(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """Send a single-turn chat request and return the assistant's text."""
    client = _get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()

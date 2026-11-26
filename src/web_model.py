"""Model budgets for the public app and a no-provider demonstration mode."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException

from . import config
from .hybrid import BM25, tokenize
from .llm import chat
from .rag import Flashcard

# Use an atomic reservation. Retain yesterday's key briefly for in-flight requests.
_BUDGET_SCRIPT = """
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
if count >= tonumber(ARGV[1]) then return 0 end
redis.call('INCR', KEYS[1])
if count == 0 then redis.call('EXPIRE', KEYS[1], 172800) end
return 1
"""


class PublicModel:
    def __init__(self, redis_url: str, redis_token: str, daily_calls: int, budget_key: str):
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.daily_calls = daily_calls
        self.budget_key = budget_key

    def _reserve(self) -> None:
        now = datetime.now(timezone.utc)
        try:
            result = httpx.post(
                self.redis_url,
                json=["EVAL", _BUDGET_SCRIPT, "1", f"{self.budget_key}:{now.date()}", str(self.daily_calls)],
                headers={"Authorization": f"Bearer {self.redis_token}"},
                timeout=3,
            )
            result.raise_for_status()
            reserved = result.json()["result"]
            if type(reserved) is not int or reserved not in (0, 1):
                raise ValueError("Invalid quota response")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(503, "The model quota service is temporarily unavailable.") from None
        if reserved == 0:
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            raise HTTPException(
                429, "The daily model quota has been reached. Try again after midnight UTC.",
                {"Retry-After": str(max(1, int((tomorrow - now).total_seconds())))},
            )

    def __call__(self, system: str, prompt: str, temperature: float = 0.1) -> str:
        if len((system + prompt).encode("utf-8")) > 16_384:
            raise HTTPException(422, "This request exceeds the model context limit. Use a shorter question.")
        return chat(
            system, prompt, temperature, model=config.LLM_MODEL,
            before_request=self._reserve, max_completion_tokens=768,
        )


def _excerpts(query: str, passages, limit: int) -> list[tuple[str, str]]:
    candidates = []
    search_text = []
    seen = set()
    for passage in passages:
        heading = ""
        blocks = re.split(r"\n\s*\n|\n(?=\s*(?:#+ |[-*] |\d+[.)] ))", passage.text)
        for block in blocks:
            block = " ".join(block.split())
            if block.startswith("#"):
                heading = block.lstrip("# ")
                continue
            block = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", block)
            for sentence in re.split(r"(?<=[.!?])\s+", block):
                if 30 <= len(sentence) <= 500 and sentence not in seen:
                    seen.add(sentence)
                    candidates.append((sentence, passage.source))
                    search_text.append(f"{heading} {sentence}")
    if not candidates or not tokenize(query):
        return []
    rank = BM25(search_text).rank(query)
    return [candidates[i] for i in rank[:limit]]


def demo_answer(query: str, passages) -> str:
    excerpts = _excerpts(query, passages, 3)
    if not excerpts:
        return "I couldn’t find a matching excerpt in your notes."
    return "**Relevant excerpts**\n\n" + "\n".join(f"- {text} [{source}]" for text, source in excerpts)


def demo_cards(query: str, passages, count: int) -> list[Flashcard]:
    cards = []
    for text, source in _excerpts(query, passages, count):
        text = text.replace("**", "").replace("`", "")
        words = list(re.finditer(r"\b[^\W\d_]{6,}\b", text))
        if words:
            word = max(words, key=lambda item: len(item[0]))
            question = text[:word.start()] + "____" + text[word.end():]
            cards.append(Flashcard(question, f"{word[0]} [{source}]"))
    return cards

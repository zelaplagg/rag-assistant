"""Structure-aware chunking for Markdown-like notes (standard library only).

Every chunk starts with its heading path ("Lecture > Types of learning"), so a chunk is
understandable on its own, and list items / paragraphs are never cut in the middle unless a
single block is longer than the chunk size. Text without headings falls back to paragraph packing.
"""
from __future__ import annotations

import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_LIST_ITEM = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+")


def split_sections(text: str) -> list[tuple[list[str], str]]:
    """Return (heading path, body) for every section that has body text."""
    sections: list[tuple[list[str], str]] = []
    stack: list[tuple[int, str]] = []
    body: list[str] = []
    in_fence = False

    def flush():
        text_ = "\n".join(body).strip()
        if text_:
            sections.append(([t for _, t in stack], text_))
        body.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip("# ").strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            body.append(line)
    flush()
    return sections


def _blocks(body: str) -> list[str]:
    """Paragraphs and list items, each kept whole (continuation lines stay with their item)."""
    blocks: list[str] = []
    cur: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            if cur:
                blocks.append("\n".join(cur))
                cur = []
        elif _LIST_ITEM.match(line) and cur:
            blocks.append("\n".join(cur))
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def _split_long(block: str, limit: int) -> list[str]:
    """Last resort for a single block longer than `limit`: split at sentence ends, then at spaces."""
    parts: list[str] = []
    cur = ""
    for sent in re.split(r"(?<=[.!?])\s+", block):
        while len(sent) > limit:
            cut = sent.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if cur and len(cur) + 1 + len(sent) > limit:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        parts.append(cur)
    return [p for p in parts if p]


def chunk_markdown(text: str, chunk_size: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    for path, body in split_sections(text):
        prefix = (" > ".join(path) + "\n\n") if path else ""
        limit = max(chunk_size - len(prefix), chunk_size // 2)
        if len(body) <= limit:
            chunks.append(prefix + body)
            continue
        cur = ""
        for block in _blocks(body):
            pieces = [block] if len(block) <= limit else _split_long(block, limit)
            for piece in pieces:
                if cur and len(cur) + 2 + len(piece) > limit:
                    chunks.append(prefix + cur)
                    cur = piece
                elif cur:
                    cur += ("\n" if _LIST_ITEM.match(piece) else "\n\n") + piece
                else:
                    cur = piece
        if cur:
            chunks.append(prefix + cur)
    return chunks

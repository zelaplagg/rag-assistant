"""RAG orchestration: retrieve context, then answer / summarize / quiz with an LLM."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .retriever import retrieve, Passage
from .llm import chat

QA_SYSTEM = (
    "You are StudyMate, a friendly study tutor. Answer the student's question using "
    "ONLY the provided notes. If the notes don't contain the answer, say so honestly. "
    "Be clear and concise. After each claim, cite the note it came from using the exact "
    "file name shown in that note's header, in square brackets, for example [rag_basics.md]. "
    "Only cite file names that appear in the provided notes."
)

SUMMARY_SYSTEM = (
    "You are StudyMate, a study tutor. Using ONLY the provided notes, write concise, "
    "well-structured study notes on the topic. Use short bullet points and bold key "
    "terms. Do not invent facts that are not in the notes."
)

QUIZ_SYSTEM = (
    "You are StudyMate, a study tutor. Using ONLY the provided notes, create clear "
    "study flashcards. Return EACH card on two lines in exactly this format:\n"
    "Q: <question>\nA: <answer>\n\n"
    "Do not add numbering, commentary, or anything else."
)


@dataclass
class Answer:
    text: str
    passages: list[Passage] = field(default_factory=list)


@dataclass
class Flashcard:
    question: str
    answer: str


def _context(passages: list[Passage]) -> str:
    return "\n\n---\n\n".join(f"[{p.source}]\n{p.text}" for p in passages)


def answer_question(question: str, top_k: int | None = None) -> Answer:
    passages = retrieve(question, top_k=top_k)
    if not passages:
        return Answer("Your notes are empty — add some notes first.", [])
    prompt = (
        f"Notes:\n\n{_context(passages)}\n\n"
        f"Question: {question}\n\nAnswer (cite file names from the headers in [brackets]):"
    )
    return Answer(chat(QA_SYSTEM, prompt), passages)


def summarize(topic: str, top_k: int = 6) -> Answer:
    passages = retrieve(topic, top_k=top_k)
    if not passages:
        return Answer("Your notes are empty — add some notes first.", [])
    prompt = (
        f"Notes:\n\n{_context(passages)}\n\n"
        f"Write concise study notes summarizing everything about: {topic}"
    )
    return Answer(chat(SUMMARY_SYSTEM, prompt), passages)


def generate_flashcards(topic: str, n: int = 5, top_k: int = 6) -> tuple[list[Flashcard], list[Passage]]:
    passages = retrieve(topic, top_k=top_k)
    if not passages:
        return [], []
    prompt = (
        f"Notes:\n\n{_context(passages)}\n\n"
        f"Create {n} flashcards to help a student revise the topic: {topic}"
    )
    raw = chat(QUIZ_SYSTEM, prompt, temperature=0.3)
    return _parse_flashcards(raw), passages


def _parse_flashcards(raw: str) -> list[Flashcard]:
    """Parse 'Q: ... / A: ...' blocks leniently."""
    cards: list[Flashcard] = []
    questions = re.split(r"(?im)^\s*Q\s*[:.\-]\s*", raw)
    for block in questions[1:]:
        parts = re.split(r"(?im)^\s*A\s*[:.\-]\s*", block, maxsplit=1)
        if len(parts) == 2:
            q = parts[0].strip().strip("\n")
            a = parts[1].strip().strip("\n")
            # cut anything after a blank line that belongs to the next card
            a = a.split("\n\n")[0].strip()
            if q and a:
                cards.append(Flashcard(q, a))
    return cards

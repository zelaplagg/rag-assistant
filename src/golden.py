"""Golden evaluation set: loading and validation (standard library only).

Each case says which note(s) should answer the question and quotes the exact
`evidence` text, so retrieval can be scored independently of chunk boundaries:
a retrieved chunk "hits" if it contains an evidence phrase.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .loaders import read_file

CATEGORIES = {"factual", "paraphrase", "multi_doc", "cross_lingual", "unanswerable", "adversarial"}


@dataclass
class GoldenCase:
    id: str
    question: str
    category: str
    lang: str
    answerable: bool
    expected_sources: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    reference_answer: str = ""
    must_include: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    """Lowercase, drop markdown emphasis, collapse whitespace."""
    return re.sub(r"\s+", " ", text.replace("*", "")).strip().lower()


def contains_evidence(chunk: str, phrase: str) -> bool:
    return normalize(phrase) in normalize(chunk)


def load_golden(path: str = "data/eval/golden.json") -> list[GoldenCase]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [GoldenCase(**c) for c in raw["cases"]]


def validate(cases: list[GoldenCase], docs_dir: str = "data/docs") -> list[str]:
    """Return a list of problems (empty list = dataset is consistent with the notes)."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in cases:
        where = f"{c.id}"
        if c.id in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(c.id)
        if c.category not in CATEGORIES:
            problems.append(f"{where}: unknown category {c.category!r}")
        if not c.question.strip():
            problems.append(f"{where}: empty question")
        if c.answerable:
            if not c.expected_sources or not c.evidence:
                problems.append(f"{where}: answerable case needs expected_sources and evidence")
            if not c.must_include:
                problems.append(f"{where}: answerable case needs must_include keywords")
        elif c.expected_sources or c.evidence:
            problems.append(f"{where}: unanswerable case must have no sources/evidence")

        texts = {}
        for src in c.expected_sources:
            p = os.path.join(docs_dir, src)
            if not os.path.isfile(p):
                problems.append(f"{where}: source {src!r} not found in {docs_dir}")
            else:
                texts[src] = read_file(p)  # .md/.txt/.pdf/.docx
        for ev in c.evidence:
            if texts and not any(contains_evidence(t, ev) for t in texts.values()):
                problems.append(f"{where}: evidence not found in expected sources: {ev!r}")
    return problems

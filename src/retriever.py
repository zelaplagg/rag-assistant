"""Semantic retrieval over the Chroma vector store."""
from __future__ import annotations

from dataclasses import dataclass

from . import config
from .ingest import get_collection


@dataclass
class Passage:
    text: str
    source: str
    score: float  # cosine similarity (1.0 = identical)


def retrieve(question: str, top_k: int | None = None) -> list[Passage]:
    """Return the top_k most relevant passages for a question."""
    top_k = top_k or config.TOP_K
    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[question],
        n_results=min(top_k, collection.count()),
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    passages = []
    for text, meta, dist in zip(docs, metas, dists):
        passages.append(
            Passage(
                text=text,
                source=meta.get("source", "unknown"),
                score=round(1 - dist, 3),  # cosine distance -> similarity
            )
        )
    return passages

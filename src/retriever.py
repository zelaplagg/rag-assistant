"""Retrieval over the Chroma vector store: semantic ("vector") or hybrid (BM25 + vectors)."""
from __future__ import annotations

from dataclasses import dataclass

from . import config
from .hybrid import BM25, rrf
from .ingest import get_collection


@dataclass
class Passage:
    text: str
    source: str
    score: float  # cosine similarity (1.0 = identical); 0.0 if only the keyword search found it


def _vector_query(collection, question: str, n: int):
    res = collection.query(query_texts=[question], n_results=min(n, collection.count()))
    return (res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])


def retrieve(question: str, top_k: int | None = None, mode: str | None = None, *, collection=None) -> list[Passage]:
    """Return the top_k most relevant passages for a question.

    mode "vector": nearest chunks by embedding similarity.
    mode "hybrid": fuse the embedding ranking with a BM25 keyword ranking (reciprocal rank
    fusion). This rescues short or term-specific questions ("What is top-k?") that embeddings
    blur. The BM25 index is rebuilt per call, which is fine for notes-sized corpora.
    """
    top_k = top_k or config.TOP_K
    mode = mode or config.RETRIEVAL_MODE
    if collection is None:
        collection = get_collection()
    if collection.count() == 0:
        return []

    pool = top_k if mode == "vector" else max(top_k * 4, 20)
    ids, docs, metas, dists = _vector_query(collection, question, pool)
    by_id = {
        i: Passage(text=d, source=m.get("source", "unknown"), score=round(1 - dist, 3))
        for i, d, m, dist in zip(ids, docs, metas, dists)
    }
    if mode == "vector":
        return [by_id[i] for i in ids[:top_k]]
    if mode != "hybrid":
        raise ValueError(f"Unknown RETRIEVAL_MODE {mode!r} (use 'vector' or 'hybrid')")

    allc = collection.get(include=["documents", "metadatas"])
    a_ids, a_docs, a_metas = allc["ids"], allc["documents"], allc["metadatas"]
    for i, d, m in zip(a_ids, a_docs, a_metas):
        by_id.setdefault(i, Passage(text=d, source=m.get("source", "unknown"), score=0.0))
    bm25_order = [a_ids[j] for j in BM25(a_docs).rank(question)]
    return [by_id[i] for i in rrf([ids, bm25_order])[:top_k]]

"""Ingestion pipeline: read documents -> chunk -> embed -> store in Chroma.

Run directly to (re)build the vector store from data/docs:
    python -m src.ingest
"""
from __future__ import annotations

import os
import glob

import chromadb
from chromadb.utils import embedding_functions

from . import config
from .loaders import SUPPORTED, extract_text_from_pdf, read_file  # noqa: F401 (re-exported)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character chunks, preferring natural breaks."""
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", "\n", ". "):
                idx = window.rfind(sep)
                if idx != -1 and idx > chunk_size * 0.5:
                    end = start + idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def load_documents(docs_dir: str) -> list[tuple[str, str]]:
    """Return (filename, text) for every supported note (.md/.txt/.pdf/.docx) in a directory."""
    paths = sorted(
        p
        for ext in SUPPORTED
        for p in glob.glob(os.path.join(docs_dir, "**", f"*{ext}"), recursive=True)
    )
    docs = []
    for path in paths:
        if os.path.basename(path).startswith("~$"):  # Word lock files
            continue
        try:
            docs.append((os.path.basename(path), read_file(path)))
        except Exception as exc:  # one broken file must not stop indexing
            print(f"Skipping {path}: {exc}")
    return docs


def get_collection():
    """Return a Chroma collection backed by a local sentence-transformers model."""
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=config.EMBED_MODEL
    )
    return client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def add_text(source: str, text: str) -> int:
    """Chunk and add (upsert) a single document into the collection.

    Returns the number of chunks added. Upsert means re-adding the same
    source overwrites its chunks instead of duplicating them.
    """
    collection = get_collection()
    chunks = chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    if not chunks:
        return 0

    ids = [f"{source}::chunk-{i}" for i in range(len(chunks))]
    metadatas = [{"source": source, "chunk": i} for i in range(len(chunks))]

    batch = 128
    for s in range(0, len(chunks), batch):
        collection.upsert(
            ids=ids[s:s + batch],
            documents=chunks[s:s + batch],
            metadatas=metadatas[s:s + batch],
        )
    return len(chunks)


def ingest_sample() -> int:
    """Add the bundled sample notes (data/docs) into the collection."""
    total = 0
    for source, text in load_documents(config.DOCS_DIR):
        total += add_text(source, text)
    return total


def list_sources() -> list[str]:
    """Return the distinct source filenames currently in the collection."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    got = collection.get(include=["metadatas"])
    sources = {m.get("source", "unknown") for m in got.get("metadatas", [])}
    return sorted(sources)


def count_chunks() -> int:
    """Number of chunks currently indexed."""
    try:
        return get_collection().count()
    except Exception:
        return 0


def clear_index() -> None:
    """Delete the whole collection (removes all notes)."""
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        pass


def build_index() -> int:
    """Wipe and rebuild the vector store from data/docs. Returns chunk count."""
    clear_index()
    return ingest_sample()


if __name__ == "__main__":
    count = build_index()
    print(f"Ingested {count} chunks into collection '{config.COLLECTION_NAME}'.")

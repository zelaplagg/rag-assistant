"""HTTP API for StudyMate, used by the Angular frontend in ./frontend.

This file is a thin layer: all RAG logic stays in src/ (the same functions the Streamlit app calls).

Run with:
    uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import config
from src.ingest import add_text, clear_index, count_chunks, get_collection, ingest_sample
from src.loaders import SUPPORTED, extract_text
from src.rag import answer_question, generate_flashcards, summarize

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200").split(",") if o.strip()]

app = FastAPI(title="StudyMate API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ schemas
class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=10)


class TopicRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)


class FlashcardsRequest(TopicRequest):
    count: int = Field(default=5, ge=3, le=10)


# ------------------------------------------------------------------ helpers
def _notes() -> list[dict]:
    """Indexed files with their chunk counts."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    counts: dict[str, int] = {}
    for meta in collection.get(include=["metadatas"])["metadatas"]:
        name = meta.get("source", "unknown")
        counts[name] = counts.get(name, 0) + 1
    return [{"name": n, "chunks": c} for n, c in sorted(counts.items())]


def _require_notes() -> None:
    if count_chunks() == 0:
        raise HTTPException(status_code=400, detail="Your notes are empty. Upload a file or load the sample notes first.")


def _llm_failed(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail=(
            f"The language model '{config.LLM_MODEL}' did not answer ({type(exc).__name__}). "
            "Check that Ollama is running or that LLM_API_KEY / LLM_BASE_URL in .env are correct."
        ),
    )


def _passages(passages) -> list[dict]:
    return [{"source": p.source, "score": p.score, "text": p.text} for p in passages]


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": config.LLM_MODEL,
        "local": bool(config.LLM_BASE_URL),
        "chunks": count_chunks(),
        "formats": [s.lstrip(".") for s in SUPPORTED],
    }


@app.get("/api/notes")
def list_notes() -> list[dict]:
    return _notes()


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)) -> list[dict]:
    results = []
    for f in files:
        name = os.path.basename(f.filename or "note")
        try:
            data = await f.read()
            if len(data) > MAX_UPLOAD_BYTES:
                raise ValueError(f"File is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB.")
            if not name.lower().endswith(SUPPORTED):
                raise ValueError("Unsupported type. Use .md, .txt, .pdf or .docx.")
            chunks = add_text(name, extract_text(name, data))
            if chunks == 0:
                raise ValueError("No readable text found in this file.")
            results.append({"name": name, "chunks": chunks, "error": None})
        except Exception as exc:  # one bad file must not fail the whole batch
            results.append({"name": name, "chunks": 0, "error": str(exc)})
    return results


@app.post("/api/sample")
def load_sample() -> dict:
    return {"chunks": ingest_sample()}


@app.delete("/api/notes/{name}", status_code=204)
def delete_note(name: str) -> None:
    get_collection().delete(where={"source": name})


@app.delete("/api/notes", status_code=204)
def delete_all_notes() -> None:
    clear_index()


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    _require_notes()
    try:
        result = answer_question(req.question, top_k=req.top_k)
    except Exception as exc:
        raise _llm_failed(exc) from exc
    return {"answer": result.text, "sources": _passages(result.passages)}


@app.post("/api/summary")
def summary(req: TopicRequest) -> dict:
    _require_notes()
    try:
        result = summarize(req.topic)
    except Exception as exc:
        raise _llm_failed(exc) from exc
    return {"summary": result.text, "sources": sorted({p.source for p in result.passages})}


@app.post("/api/flashcards")
def flashcards(req: FlashcardsRequest) -> dict:
    _require_notes()
    try:
        cards, _ = generate_flashcards(req.topic, req.count)
    except Exception as exc:
        raise _llm_failed(exc) from exc
    return {"cards": [{"question": c.question, "answer": c.answer} for c in cards]}

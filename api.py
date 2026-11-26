"""Angular HTTP service with private, expiring workspaces."""
from __future__ import annotations

import asyncio
import os
from collections import Counter
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as FormUploadFile

from src import config
from src.ingest import load_documents, make_chunks
from src.loaders import SUPPORTED, sanitize
from src.rag import answer_question, generate_flashcards, summarize
from src.retriever import retrieve
from src.web_extract import extract_upload
from src.web_http import HttpGuard
from src.web_model import PublicModel, demo_answer, demo_cards
from src.web_sessions import Workspace, Workspaces, note_counts

MAX_FILES = 3
MAX_NOTES = 12
MAX_CHUNKS = 180
COOKIE = "studymate_workspace"
STATIC_DIR = Path(__file__).resolve().parent / "frontend/dist/studymate/browser"


def _env_int(key: str, default: int, ceiling: int) -> int:
    value = int(os.getenv(key, str(default)))
    if not 1 <= value <= ceiling:
        raise RuntimeError(f"{key} must be between 1 and {ceiling}.")
    return value


def _https_url(value: str) -> bool:
    url = urlsplit(value)
    return url.scheme == "https" and bool(url.hostname) and not url.username and not url.password


def _name(value: str) -> str:
    name = sanitize(value.strip())
    if name != value.strip() or not name or len(name) > 120 or any(c in name for c in '/\\[]\n\t'):
        raise ValueError("Use a filename of at most 120 characters with no slashes or brackets.")
    if Path(name).suffix.lower() not in SUPPORTED:
        raise ValueError("Unsupported type. Use .md, .txt, .pdf or .docx.")
    return name


def _add(store: Workspaces, collection, name: str, chunks: list[str], counts: Counter) -> int:
    old = counts[name]
    if not chunks:
        raise ValueError("No readable text found in this file.")
    if (not old and len(counts) >= MAX_NOTES) or sum(counts.values()) - old + len(chunks) > MAX_CHUNKS:
        raise ValueError("This workspace has reached its note or chunk limit. Delete a note and retry.")
    ids = [f"{name}::chunk-{index}" for index in range(len(chunks))]
    collection.upsert(
        ids=ids, documents=chunks, embeddings=store.embed(chunks),
        metadatas=[{"source": name, "chunk": index} for index in range(len(chunks))],
    )
    if old > len(chunks):
        collection.delete(ids=[f"{name}::chunk-{index}" for index in range(len(chunks), old)])
    counts[name] = len(chunks)
    return len(chunks)


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("question", "topic", check_fields=False)
    @classmethod
    def visible_text(cls, value: str) -> str:
        value = sanitize(value).strip()
        if not value:
            raise ValueError("Enter a question or topic.")
        return value


class AskRequest(Input):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=10, strict=True)


class TopicRequest(Input):
    topic: str = Field(min_length=1, max_length=300)


class FlashcardsRequest(TopicRequest):
    count: int = Field(default=5, ge=3, le=10, strict=True)


def create_app(*, embedder=None) -> FastAPI:
    public = os.getenv("STUDYMATE_PUBLIC", "0") == "1"
    origin = os.getenv("STUDYMATE_ORIGIN") or os.getenv("RENDER_EXTERNAL_URL")
    allowed = os.getenv("CORS_ORIGINS", "" if public else "http://localhost:4200,http://127.0.0.1:4200")
    origins = {value.strip().rstrip("/") for value in allowed.split(",") if value.strip()}
    if any("*" in value or (public and not _https_url(value)) for value in origins):
        raise RuntimeError("CORS_ORIGINS must contain explicit origins. Public origins must use HTTPS.")
    if origin and public and not _https_url(origin):
        raise RuntimeError("STUDYMATE_ORIGIN must use HTTPS.")

    # A public service without a provider key launches the no-spend demo.
    mode = os.getenv("STUDYMATE_MODE", "demo" if public and not config.LLM_API_KEY else "llm")
    if mode not in {"llm", "demo"}:
        raise RuntimeError("STUDYMATE_MODE must be 'llm' or 'demo'.")
    model = None
    if mode == "llm" and public:
        redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "")
        redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        if not config.LLM_API_KEY or not _https_url(redis_url) or not redis_token:
            raise RuntimeError("Public LLM mode requires LLM_API_KEY and an HTTPS Upstash Redis REST URL and token.")
        if config.LLM_BASE_URL and not _https_url(config.LLM_BASE_URL):
            raise RuntimeError("The public LLM endpoint must use HTTPS.")
        model = PublicModel(
            redis_url, redis_token, _env_int("LLM_DAILY_CALLS", 100, 1000),
            os.getenv("LLM_BUDGET_KEY", "studymate:public:model-calls"),
        )

    max_upload = _env_int("MAX_UPLOAD_MB", 2, 10) * 1024 * 1024
    ttl = _env_int("SESSION_TTL_SECONDS", 3600, 86_400)
    capacity = _env_int("MAX_WORKSPACES", 24, 100)

    async def cleanup(store: Workspaces) -> None:
        while True:
            await asyncio.sleep(min(ttl, 30))
            await run_in_threadpool(store.prune)

    @asynccontextmanager
    async def lifespan(service: FastAPI):
        store = Workspaces(capacity, ttl, embedder=embedder)
        await run_in_threadpool(store.warm)
        service.state.workspaces = store
        task = asyncio.create_task(cleanup(store))
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="StudyMate API", version="1.1.0", lifespan=lifespan,
        docs_url=None if public else "/docs", redoc_url=None if public else "/redoc",
        openapi_url=None if public else "/openapi.json",
    )
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=sorted(origins), allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
        )
    app.add_middleware(
        HttpGuard, public=public, origin=origin.rstrip("/") if origin else None,
        origins=origins, upload_limit=MAX_FILES * max_upload + 65_536,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        fields = sorted({str(err["loc"][-1]) for err in exc.errors() if err["loc"]})
        return JSONResponse({"detail": "Check the request fields: " + ", ".join(fields) + "."}, status_code=422)

    def workspace(request: Request, response: Response):
        store = request.app.state.workspaces
        path = request.url.path
        category = {
            "/api/upload": "writes", "/api/sample": "writes",
            "/api/ask": "generations", "/api/summary": "generations", "/api/flashcards": "generations",
        }.get(path)
        with store.lease(request.cookies.get(COOKIE), request.method == "GET" and path == "/api/notes", category) as lease:
            work, new_token = lease
            if new_token is not None:
                response.set_cookie(COOKIE, new_token, max_age=ttl, secure=public, httponly=True, samesite="strict", path="/api")
            yield work

    def require_collection(store: Workspaces, work: Workspace):
        collection = store.collection(work)
        if collection is None or collection.count() == 0:
            raise HTTPException(400, "Your notes are empty. Upload a file or load the sample notes first.")
        return collection

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "mode": mode, "model": config.LLM_MODEL if mode == "llm" else "Extractive demo",
                "formats": [item[1:] for item in SUPPORTED], "maxUploadBytes": max_upload, "maxFiles": MAX_FILES,
                "sessionSeconds": ttl, "hosted": public}

    @app.get("/api/notes")
    def list_notes(request: Request, work: Workspace = Depends(workspace)) -> list[dict]:
        counts = note_counts(request.app.state.workspaces.collection(work))
        return [{"name": name, "chunks": count} for name, count in sorted(counts.items())]

    @app.post("/api/upload")
    async def upload(request: Request, work: Workspace = Depends(workspace)) -> list[dict]:
        def index(name: str, data: bytes) -> int:
            chunks = make_chunks(extract_upload(Path(name).suffix.lower(), data))
            store = request.app.state.workspaces
            collection = store.collection(work, create=True)
            return _add(store, collection, name, chunks, note_counts(collection))

        results = []
        async with request.form(max_files=MAX_FILES, max_fields=0, max_part_size=max_upload) as form:
            for field, upload_file in form.multi_items():
                if field != "files" or not isinstance(upload_file, FormUploadFile):
                    raise HTTPException(422, "Submit each upload in a files field.")
            for upload_file in form.getlist("files"):
                name = (upload_file.filename or "Note")[:120]
                try:
                    name = _name(upload_file.filename or "")
                    data = await upload_file.read(max_upload + 1)
                    if len(data) > max_upload:
                        raise ValueError(f"The file exceeds {max_upload // 1024**2} MB.")
                    chunks = await run_in_threadpool(index, name, data)
                    results.append({"name": name, "chunks": chunks, "error": None})
                except ValueError as exc:
                    results.append({"name": name, "chunks": 0, "error": str(exc)})
        if not results:
            raise HTTPException(422, "Choose at least one file.")
        return results

    @app.post("/api/sample")
    def load_sample(request: Request, work: Workspace = Depends(workspace)) -> dict:
        documents = [(name, make_chunks(text)) for name, text in load_documents(config.DOCS_DIR) if text.strip()]
        if not documents:
            raise HTTPException(503, "The sample notes are unavailable.")
        store = request.app.state.workspaces
        collection = store.collection(work, create=True)
        counts = note_counts(collection)
        sample_names = {name for name, _ in documents}
        unchanged = Counter({name: count for name, count in counts.items() if name not in sample_names})
        if len(unchanged) + len(documents) > MAX_NOTES or sum(unchanged.values()) + sum(len(c) for _, c in documents) > MAX_CHUNKS:
            raise HTTPException(409, "Delete some notes before loading the sample library.")
        try:
            # Remove surplus chunks first when replacing a sample with a shorter original.
            ordered = sorted(documents, key=lambda doc: len(doc[1]) - counts[doc[0]])
            return {"chunks": sum(_add(store, collection, name, chunks, counts) for name, chunks in ordered)}
        except ValueError:
            raise HTTPException(409, "The sample notes exceed the workspace limits.") from None

    @app.delete("/api/notes/{name}", status_code=204)
    def delete_note(name: str, request: Request, work: Workspace = Depends(workspace)) -> None:
        collection = request.app.state.workspaces.collection(work)
        if collection is not None:
            collection.delete(where={"source": name})

    @app.delete("/api/notes", status_code=204)
    def delete_all_notes(request: Request, work: Workspace = Depends(workspace)) -> None:
        request.app.state.workspaces.clear(work)

    def generate(operation, *args, **kwargs):
        try:
            return operation(*args, generate=model, **kwargs)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "The language model is temporarily unavailable.") from None

    @app.post("/api/ask")
    def ask(req: AskRequest, request: Request, work: Workspace = Depends(workspace)) -> dict:
        collection = require_collection(request.app.state.workspaces, work)
        if mode == "demo":
            passages = retrieve(req.question, top_k=req.top_k, collection=collection)
            answer = demo_answer(req.question, passages)
        else:
            result = generate(answer_question, req.question, top_k=req.top_k, collection=collection)
            passages, answer = result.passages, result.text
        return {"answer": answer, "sources": [{"source": p.source, "score": p.score, "text": p.text} for p in passages]}

    @app.post("/api/summary")
    def summary(req: TopicRequest, request: Request, work: Workspace = Depends(workspace)) -> dict:
        collection = require_collection(request.app.state.workspaces, work)
        if mode == "demo":
            passages = retrieve(req.topic, top_k=6, collection=collection)
            text = demo_answer(req.topic, passages)
        else:
            result = generate(summarize, req.topic, collection=collection)
            passages, text = result.passages, result.text
        return {"summary": text, "sources": sorted({p.source for p in passages})}

    @app.post("/api/flashcards")
    def flashcards(req: FlashcardsRequest, request: Request, work: Workspace = Depends(workspace)) -> dict:
        collection = require_collection(request.app.state.workspaces, work)
        if mode == "demo":
            cards = demo_cards(req.topic, retrieve(req.topic, top_k=6, collection=collection), req.count)
        else:
            cards, _ = generate(generate_flashcards, req.topic, req.count, collection=collection)
        return {"cards": [{"question": card.question, "answer": card.answer} for card in cards]}

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found() -> None:
        raise HTTPException(404, "API route not found.")

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
    elif public:
        raise RuntimeError("The Angular production build is missing.")
    return app


app = create_app()

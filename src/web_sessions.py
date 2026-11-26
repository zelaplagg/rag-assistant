"""Bounded anonymous workspaces for the HTTP app. The CLI keeps its local index."""
from __future__ import annotations

import os
import secrets
import threading
import time
from collections import Counter, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from fastapi import HTTPException


class Window:
    """A sliding-window limit. Call under the owning lock."""

    def __init__(self, limit: int, seconds: int = 60):
        self.limit = limit
        self.seconds = seconds
        self.events: deque[float] = deque()

    def take(self, now: float) -> None:
        while self.events and self.events[0] <= now - self.seconds:
            self.events.popleft()
        if len(self.events) >= self.limit:
            wait = max(1, int(self.events[0] + self.seconds - now) + 1)
            raise HTTPException(429, "Too many requests. Try again shortly.", {"Retry-After": str(wait)})
        self.events.append(now)


@dataclass
class Workspace:
    collection_name: str
    expires: float
    requests: Window = field(default_factory=lambda: Window(30))
    writes: Window = field(default_factory=lambda: Window(5))
    generations: Window = field(default_factory=lambda: Window(6))
    busy: bool = False


def web_embedder():
    embedder = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
    embedder.DOWNLOAD_PATH = Path(os.getenv("STUDYMATE_MODEL_CACHE", ".cache/studymate-onnx"))
    return embedder


class Workspaces:
    def __init__(self, capacity: int, ttl: int, embedder=None):
        self.capacity = capacity
        self.ttl = ttl
        self._lock = threading.Lock()
        self._workspaces: dict[str, Workspace] = {}
        self._new_sessions = Window(20)
        self._embedder = embedder if embedder is not None else web_embedder()
        self._client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        self._collections: dict[str, chromadb.Collection] = {}

    def warm(self) -> None:
        self._embedder(["StudyMate"])

    def embed(self, texts: list[str]) -> list:
        # Keep the ONNX attention tensors small on a 512 MiB service.
        batch_size = 4
        vectors = []
        for start in range(0, len(texts), batch_size):
            vectors.extend(self._embedder(texts[start:start + batch_size]))
        return vectors

    def prune(self) -> None:
        with self._lock:
            self._prune(time.monotonic())

    def _prune(self, now: float) -> None:
        for token, workspace in list(self._workspaces.items()):
            if workspace.expires <= now and not workspace.busy:
                self.clear(workspace)
                del self._workspaces[token]

    @contextmanager
    def lease(self, token: str | None, allow_create: bool, category: str | None):
        with self._lock:
            now = time.monotonic()
            workspace = self._workspaces.get(token)
            new_token = None
            if workspace is None or workspace.expires <= now:
                if not allow_create:
                    raise HTTPException(401, "Your workspace expired. Refresh the page to start a new one.")
                self._prune(now)
                self._new_sessions.take(now)
                if len(self._workspaces) >= self.capacity:
                    unused = next((key for key, value in self._workspaces.items()
                                   if not value.busy and value.collection_name not in self._collections), None)
                    if unused is None:
                        raise HTTPException(503, "All demo workspaces are in use. Try again later.", {"Retry-After": "60"})
                    del self._workspaces[unused]
                new_token = secrets.token_urlsafe(32)
                workspace = Workspace("web-" + secrets.token_hex(24), now + self.ttl)
                self._workspaces[new_token] = workspace
            if workspace.busy:
                raise HTTPException(429, "Your workspace has a request in progress.", {"Retry-After": "2"})
            workspace.requests.take(now)
            if category is not None:
                getattr(workspace, category).take(now)
            workspace.busy = True

        try:
            yield workspace, new_token
        finally:
            with self._lock:
                workspace.busy = False

    def collection(self, workspace: Workspace, *, create: bool = False):
        name = workspace.collection_name
        if create and name not in self._collections:
            self._collections[name] = self._client.create_collection(
                name,
                embedding_function=self._embedder,
                configuration={"hnsw": {"space": "cosine", "num_threads": 1}},
            )
        return self._collections.get(name)

    def clear(self, workspace: Workspace) -> None:
        name = workspace.collection_name
        if name in self._collections:
            self._client.delete_collection(name)
            del self._collections[name]


def note_counts(collection) -> Counter:
    if collection is None:
        return Counter()
    return Counter(row["source"] for row in collection.get(include=["metadatas"])["metadatas"])

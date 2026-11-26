import io
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from chromadb.api.types import EmbeddingFunction
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api
from src.web_model import PublicModel


class TestEmbedding(EmbeddingFunction):
    def __init__(self):
        self.vector = [1.0, 0.5, 0.25]

    @staticmethod
    def name():
        return "test-embedding"

    def __call__(self, input):
        return [self.vector for _ in input]

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(_config):
        return TestEmbedding()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(build.cleanup)
        Path(build.name, "index.html").write_text("<title>StudyMate</title>", encoding="utf-8")
        with patch.object(api, "STATIC_DIR", Path(build.name)), patch.dict("os.environ", {
            "STUDYMATE_PUBLIC": "1", "STUDYMATE_MODE": "demo",
            "STUDYMATE_ORIGIN": "https://studymate.test", "CORS_ORIGINS": "",
        }):
            cls.app = api.create_app(embedder=TestEmbedding())
        cls.server = TestClient(cls.app, base_url="https://studymate.test")
        cls.server.__enter__()
        cls.addClassCleanup(cls.server.__exit__, None, None, None)

    def new_workspace(self):
        client = TestClient(self.app, base_url="https://studymate.test")
        self.addCleanup(client.close)
        response = client.get("/api/notes")
        self.assertEqual(response.json(), [])
        for attr in ("httponly", "samesite=strict", "secure"):
            self.assertIn(attr, response.headers["set-cookie"].lower())
        return client

    def test_headers_and_health(self):
        health = self.server.get("/api/health")
        self.assertEqual(health.json()["mode"], "demo")
        self.assertNotIn("set-cookie", health.headers)
        self.assertEqual(health.headers["cache-control"], "no-store")
        self.assertEqual(self.server.get("/docs").status_code, 404)
        self.assertEqual(self.server.get("/api/missing").status_code, 404)
        self.assertIn("frame-ancestors 'none'", self.server.get("/").headers["content-security-policy"])

    def test_note_names_passages_and_deletion_are_workspace_scoped(self):
        alice, bob = self.new_workspace(), self.new_workspace()
        for client, color in [(alice, "amaranth"), (bob, "sapphire")]:
            contents = f"The study guide uses the color {color} for identifying lecture material."
            upload = client.post("/api/upload", files=[("files", ("lecture.md", contents))])
            self.assertEqual(upload.json(), [{"name": "lecture.md", "chunks": 1, "error": None}])
        answer = alice.post("/api/ask", json={"question": "What color identifies lecture material?"})
        self.assertIn("amaranth", answer.json()["sources"][0]["text"])
        self.assertNotIn("sapphire", answer.text)
        self.assertEqual(bob.delete("/api/notes/lecture.md").status_code, 204)
        self.assertEqual(bob.get("/api/notes").json(), [])
        self.assertEqual(alice.get("/api/notes").json(), [{"name": "lecture.md", "chunks": 1}])
        self.assertEqual(alice.delete("/api/notes").status_code, 204)
        self.assertEqual(alice.get("/api/notes").json(), [])

    def test_missing_session_and_foreign_origin(self):
        self.assertEqual(self.server.post("/api/sample", json={}).status_code, 401)
        client = self.new_workspace()
        result = client.post("/api/sample", json={}, headers={"Origin": "https://other.test"})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(client.get("/api/notes").json(), [])

    def test_sample_notes_across_all_study_tools(self):
        client = self.new_workspace()
        self.assertGreater(client.post("/api/sample", json={}).json()["chunks"], 0)
        answer = client.post("/api/ask", json={"question": "How does a RAG pipeline work?"}).json()
        self.assertIn("[rag_basics.md]", answer["answer"])
        summary = client.post("/api/summary", json={"topic": "RAG pipeline"}).json()
        self.assertIn("[rag_basics.md]", summary["summary"])
        cards = client.post("/api/flashcards", json={"topic": "RAG pipeline", "count": 3}).json()["cards"]
        self.assertGreater(len(cards), 0)
        self.assertIn("____", cards[0]["question"])

    def test_rejects_invalid_json_fields_and_uploads(self):
        client = self.new_workspace()
        self.assertEqual(client.post("/api/ask", json={"question": " \u200b "}).status_code, 422)
        self.assertEqual(client.post("/api/ask", json={"question": "RAG?", "top_k": 11}).status_code, 422)
        self.assertEqual(client.post("/api/ask", json={"question": "x" * 15_000}).status_code, 413)
        result = client.post("/api/upload", files=[
            ("files", ("fake.pdf", b"plain text", "application/pdf")),
            ("files", ("oversize.txt", b"a" * (2 * 1024 * 1024 + 1))),
            ("files", ("../escape.md", b"# content")),
        ])
        self.assertEqual(result.status_code, 200)
        self.assertTrue(all(record["error"] for record in result.json()))
        self.assertEqual(client.get("/api/notes").json(), [])

    def test_streamed_body_limit_and_docx_extraction(self):
        client = self.new_workspace()
        result = client.post(
            "/api/ask", content=iter([b"x" * 8_000, b"y" * 8_000]),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(result.status_code, 413)
        doc = io.BytesIO()
        with zipfile.ZipFile(doc, "w") as archive:
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>StudyMate DOCX sample.</w:t></w:r></w:p></w:body></w:document>',
            )
        result = client.post("/api/upload", files=[("files", ("notes.docx", doc.getvalue()))])
        self.assertIsNone(result.json()[0]["error"])

    def test_rate_limit_and_expired_session(self):
        client = self.new_workspace()
        for _ in range(6):
            self.assertEqual(client.post("/api/ask", json={"question": "Question?"}).status_code, 400)
        result = client.post("/api/ask", json={"question": "Question?"})
        self.assertEqual(result.status_code, 429)
        self.assertGreater(int(result.headers["retry-after"]), 0)
        store = self.app.state.workspaces
        token = client.cookies[api.COOKIE]
        with store._lock:
            store._workspaces[token].expires = time.monotonic() - 1
        store.prune()
        self.assertEqual(client.post("/api/sample", json={}).status_code, 401)
        self.assertEqual(client.get("/api/notes").json(), [])
        self.assertNotEqual(client.cookies[api.COOKIE], token)


class ModelBudgetTests(unittest.TestCase):
    def setUp(self):
        self.model = PublicModel("https://redis.test", "test-token", 5, "test:budget")

    def test_live_mode_fails_closed_without_quota_configuration(self):
        with patch.dict("os.environ", {
            "STUDYMATE_PUBLIC": "1", "STUDYMATE_MODE": "llm",
            "UPSTASH_REDIS_REST_URL": "", "UPSTASH_REDIS_REST_TOKEN": "",
        }), self.assertRaisesRegex(RuntimeError, "requires LLM_API_KEY"):
            api.create_app()

    def test_model_is_called_only_after_reservation(self):
        client = Mock()
        client.with_options.return_value = client
        client.chat.completions.create.return_value.choices = [Mock(message=Mock(content="answer"))]
        request = httpx.Request("POST", "https://redis.test")
        with patch("src.llm._get_client", return_value=client):
            with patch("src.web_model.httpx.post", return_value=httpx.Response(200, json={"result": 0}, request=request)):
                with self.assertRaises(HTTPException) as caught:
                    self.model("Study tutor", "Sample notes")
            self.assertEqual(caught.exception.status_code, 429)
            client.chat.completions.create.assert_not_called()
            with patch("src.web_model.httpx.post", side_effect=httpx.ConnectError("unreachable")):
                with self.assertRaises(HTTPException) as caught:
                    self.model("Study tutor", "Sample notes")
            self.assertEqual(caught.exception.status_code, 503)
            client.chat.completions.create.assert_not_called()
            with patch("src.web_model.httpx.post", return_value=httpx.Response(200, json={"result": 1}, request=request)):
                self.assertEqual(self.model("Study tutor", "Sample notes"), "answer")
        self.assertEqual(client.chat.completions.create.call_args.kwargs["max_completion_tokens"], 768)
        client.with_options.assert_called_with(max_retries=0, timeout=25.0)

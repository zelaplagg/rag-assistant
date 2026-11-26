# Deploy StudyMate

The Docker image runs the Angular build and FastAPI under one HTTPS origin. Angular calls the relative `/api` path, and Render terminates TLS. The service runs one Uvicorn worker and uses Chroma in memory. Each anonymous browser gets its own workspace and vector collection. The web image uses the ONNX build of all-MiniLM-L6-v2 to avoid a PyTorch runtime and downloads the checksum-verified model during the image build.

## Run the public demo locally

```bash
docker build -t studymate .
docker run --rm --name studymate -p 127.0.0.1:10000:10000 \
  -e STUDYMATE_PUBLIC=0 -e STUDYMATE_MODE=demo studymate
curl -fsS http://127.0.0.1:10000/api/health
```

Open http://127.0.0.1:10000. Local HTTP mode permits a non-Secure session cookie and API documentation. Leave the container’s public default enabled behind HTTPS.

## Deploy the free demo on Render

1. Connect the GitHub repository in the [Render dashboard](https://dashboard.render.com/). Create a **Blueprint** from the branch containing the deployment files. The checked-in [render.yaml](../render.yaml) selects a Free Docker Web Service in Frankfurt and the `/api/health` health check.
2. Confirm the service name and the **Free** plan before applying. Select the branch or commit you reviewed. Automatic deployments are disabled in the Blueprint.
3. Wait for a successful deployment and copy the HTTPS URL shown on the service overview. From a signed-out browser, open that URL, click **Load sample notes**, and ask **How does a RAG pipeline work?** Expand the answer’s sources and try **Summary** and **Flashcards** with the topic **RAG pipeline**.
4. Open a second browser profile or incognito window, confirm its library starts empty, and upload a small UTF-8 `.txt` in one profile. Confirm the other library is unaffected by the upload and deletion. Check `/api/health` for `status: ok`.

The Free service sleeps after 15 minutes of inactivity. Render reports that waking it can take about one minute. Cold starts, restarts, and deploys reset anonymous workspaces. Free compute has limited throughput and monthly limits. These constraints suit a recruiter demo. [Render free service limits](https://render.com/docs/free)

For a custom domain, set `STUDYMATE_ORIGIN` to its full HTTPS origin and use that origin for public testing. With the default Render hostname, `RENDER_EXTERNAL_URL` supplies the origin. When rolling back, select a previously verified deploy in Render. A restart or rollback clears current workspaces.

## Enable live LLM generation

The shipped blueprint uses extractive demo mode. Q&A quotes retrieved text, Summary selects relevant excerpts, and Flashcards blanks terms from matching passages. It makes zero LLM calls. Live mode enables the original LLM-generated answers, summaries, and flashcards using the same retrieval and prompt modules as the CLI.

Set the following in the host’s environment dashboard. Treat the API key and Redis token as secrets. Keep them out of Git, browser code, container build arguments, and screenshots. Use a dedicated provider project and key, choose a supported model and spending policy, and give the service a Redis database that retains quota keys. Upstash’s Free Redis tier is sufficient for the default call cap under normal demo traffic. [Upstash Redis pricing](https://upstash.com/pricing/redis)

| Variable | Public service value |
| --- | --- |
| `STUDYMATE_PUBLIC` | `1` for HTTPS deployment |
| `STUDYMATE_MODE` | `demo` for the no-provider mode, `llm` for live generation |
| `STUDYMATE_ORIGIN` | Optional canonical HTTPS origin. Render supplies its default URL |
| `CORS_ORIGINS` | Empty for same-origin hosting. An optional comma-separated list of exact HTTPS origins |
| `LLM_MODEL` | An approved OpenAI-compatible chat model that accepts `max_completion_tokens` |
| `LLM_BASE_URL` | Empty for OpenAI, or an HTTPS OpenAI-compatible base URL |
| `LLM_API_KEY` | Provider key (secret, required in public `llm` mode) |
| `UPSTASH_REDIS_REST_URL` | HTTPS endpoint for the quota database (required in public `llm` mode) |
| `UPSTASH_REDIS_REST_TOKEN` | Redis write token (secret, required in public `llm` mode) |
| `LLM_DAILY_CALLS` | Global reservation cap, default 100 per UTC day, maximum 1,000 |
| `LLM_BUDGET_KEY` | Stable quota key prefix for this deployment, default `studymate:public:model-calls` |
| `MAX_UPLOAD_MB` | Per-file limit, default 2 MiB, maximum 10 MiB |
| `SESSION_TTL_SECONDS` | Absolute session lifetime, default 3,600 seconds, maximum 86,400 |
| `MAX_WORKSPACES` | Concurrent guest workspace limit, default 24, maximum 100 |
| `PORT` | Set by the host, default 10000 |

Public live mode reserves a quota slot in Redis before each provider call, including the temperature compatibility retry. A quota outage blocks generation and a depleted quota returns HTTP 429. The web path bounds prompt size, caps completion output at 768 tokens, disables SDK retries, and uses a provider timeout. The cap counts attempts and persists across app restarts while the quota database retains its keys. A dollar cap also depends on provider pricing and key use. Keep the key dedicated and configure a provider spend limit if available. The feature is compatible with a provider such as Groq that offers a free tier and OpenAI compatibility. Check model availability, account limits, and data retention before enabling it. [Groq rate limits](https://console.groq.com/docs/rate-limits) · [Groq data controls](https://console.groq.com/docs/your-data)

## Privacy and operations

- An opaque, Secure, HttpOnly, SameSite cookie identifies the workspace. All note and retrieval operations are scoped to that workspace. Same-browser tabs share it. The application stores extracted text and embeddings in memory until deletion, expiry, or restart. Raw multipart files may use temporary spool files while being parsed.
- The API limits request size before multipart parsing, allows up to three files per request, and caps each workspace at 12 documents and 180 chunks. PDF and DOCX extraction run in resource-limited subprocesses with page, archive entry, and extracted text limits. Image-only PDFs require a text layer.
- Per-workspace and global limits bound requests and concurrent processing. On Free compute a write or generation can temporarily return HTTP 429 while another request is active. Use the returned `Retry-After` where available.
- In live mode the provider receives the question or topic and retrieved excerpts. Use nonsensitive sample material when sharing the public demo. The Redis quota database receives counters only.
- Keep the deployed service at one worker and one replica because workspace data and ordinary rate limits are in memory. A multi-replica or durable user-account deployment would require shared auth, storage and rate limiting. The existing CLI and Streamlit workflows keep using their own local Chroma store under `CHROMA_DIR`.
- Keep Chroma embedded. The pinned package has open advisories in its standalone HTTP API and server authorization. The image launches only StudyMate's FastAPI app, and its collection names and embedding configuration are server-controlled. [Chroma server advisories](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c)

## Verification commands

```bash
python -m pip install -r requirements-production.txt
python -m unittest discover -s tests -t .
python -m unittest discover -s web_tests -v
cd frontend && npm ci && npm run build && npm audit --omit=dev
```

The retrieval benchmark and optional provider-backed answer evaluation still use `requirements.txt` and the commands in the [main README](../README.md#evaluation). Keep benchmark runs separate from the public model key and quota.

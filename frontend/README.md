# StudyMate — Angular frontend

A web UI for the StudyMate RAG assistant: upload notes, ask questions with cited sources, generate summaries and study flashcards.
It talks to the Python RAG code in `../src` through a FastAPI service (`../api.py`), so the Streamlit app and this UI share the retrieval and prompt modules.

```
Angular 20 (signals, standalone components)  ──HTTP/JSON──▶  FastAPI (api.py)  ──▶  src/  (hybrid retrieval · ChromaDB · LLM)
        http://localhost:4200                                http://localhost:8000
```

## Run it

Two terminals, from the project root (`rag-assistant/`):

```bash
# 1) API (first install: pip install -r requirements-production.txt)
source venv/bin/activate
STUDYMATE_MODE=demo uvicorn api:app --reload --port 8000

# 2) UI   (once: cd frontend && npm ci)
cd frontend
npm start            # http://localhost:4200
```

Set `STUDYMATE_MODE=llm` to use the OpenAI-compatible model configured in `.env`, including local Ollama.
No notes yet? Click **Load sample notes** in the sidebar.

## Features

- **Ask** — chat over your notes; answers render Markdown, file citations like `[rag_basics.md]` become badges, and each answer lists the retrieved passages with a match score.
- **Summary** — short study notes for a topic, with the files they are based on.
- **Flashcards** — 3 to 10 cards per topic; flip cards, sort them into *Got it* / *Again*, progress bar, keyboard shortcuts (Space = flip, 1 = again, 2 = got it).
- **Library** — drag & drop upload (`.md .txt .pdf .docx`), per-file delete, clear all.
- Light and dark theme, responsive layout, clear error messages when the API or the LLM is unreachable.

## API

The development server proxies the relative `/api` path to port 8000. In production the API serves the Angular build. The first `GET /api/notes` establishes a private workspace cookie.

See the [deployment guide](../docs/deployment.md) for production setup and reaching the demo.


| Method & path | Body | Returns |
|---|---|---|
| `GET /api/health` | – | mode, model, formats and workspace limits |
| `GET /api/notes` | – | `[{name, chunks}]` |
| `POST /api/upload` | multipart `files` | per-file `{name, chunks, error}` |
| `POST /api/sample` | – | `{chunks}` |
| `DELETE /api/notes/{name}` · `DELETE /api/notes` | – | 204 |
| `POST /api/ask` | `{question, top_k?}` | `{answer, sources: [{source, score, text}]}` |
| `POST /api/summary` | `{topic}` | `{summary, sources}` |
| `POST /api/flashcards` | `{topic, count}` | `{cards: [{question, answer}]}` |

Interactive docs: http://localhost:8000/docs

## Structure

```
frontend/src/app/
  store.ts        all UI state as Angular signals + the actions that call the API
  api.service.ts  typed HttpClient wrapper
  models.ts       request / response types
  app.ts          shell: header, tabs, toasts
  library.ts      upload + notes list     ask.ts   chat     summary.ts   flashcards.ts
  markdown.ts     small safe Markdown renderer (no innerHTML)
  icon.ts         inline SVG icons
```

## Design notes

- **Signals instead of RxJS state.** Components read signals from one `Store`; HTTP calls are awaited with `firstValueFrom`, which keeps loading and error handling linear.
- **No `innerHTML`.** LLM output is parsed into blocks and rendered with Angular bindings, so a model (or a prompt-injected note) can't inject HTML.
- **The RAG code is untouched.** `api.py` only calls the functions the Streamlit app already uses.

## Limitations

- Local, single-user: no authentication, one shared index.
- Answers are not streamed; the UI shows a typing indicator until the full answer arrives.
- No automated frontend tests yet.

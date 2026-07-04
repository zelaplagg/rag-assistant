# 📚 StudyMate — AI Study Assistant for Your Notes

> Turn your lecture notes into an interactive tutor. Upload your notes and StudyMate
> lets you **ask questions**, **generate summaries**, and **create flashcards** — all
> grounded in your own material, with source citations. Powered by
> **Retrieval-Augmented Generation (RAG)**.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![RAG](https://img.shields.io/badge/RAG-Retrieval--Augmented%20Generation-purple)
![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-success)
![Embeddings](https://img.shields.io/badge/Embeddings-sentence--transformers-orange)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![Local LLM](https://img.shields.io/badge/LLM-Local%20via%20Ollama-lightgrey)

---

## Why StudyMate?

Studying from long lecture notes is slow. StudyMate turns a pile of notes into an
assistant you can talk to: it finds the relevant passages for any question and uses
a language model to answer, summarize, or quiz you — while always showing which note
the answer came from, so you can trust and verify it.

Everything can run **fully locally and free** (embeddings + a local LLM via Ollama),
so your notes never leave your machine.

## Features

- 💬 **Ask your notes** — chat-style Q&A grounded in your uploaded material.
- 📝 **Instant summaries** — generate concise study notes on any topic.
- 🎴 **Auto flashcards** — create question/answer cards to test yourself.
- 📎 **Source citations** — every answer shows the notes it came from.
- 📁 **Bring your own notes** — upload `.md`, `.txt`, or `.pdf` from the UI.
- 🔒 **Private & local** — runs with a local model; no API key required.

## How it works (RAG pipeline)

```text
        ┌───────────┐    ┌────────────┐    ┌──────────────┐
notes ─▶│ Chunking  │───▶│ Embeddings │───▶│  Vector DB   │
        └───────────┘    └────────────┘    │  (ChromaDB)  │
                                           └──────┬───────┘
                                                  │ top-k similar
question ─▶ embed ─▶ semantic search ─────────────┘
                                                  │
                                          ┌───────▼────────┐
                                          │  Prompt + LLM  │─▶ answer / summary /
                                          │  (generation)  │   flashcards + sources
                                          └────────────────┘
```

1. **Chunk** notes into overlapping passages.
2. **Embed** each passage into a vector with `sentence-transformers`.
3. **Store & search** vectors in ChromaDB using cosine similarity.
4. **Retrieve** the most relevant passages for a query.
5. **Generate** a grounded answer, summary, or flashcards with an LLM.

## Tech Stack

- **Python 3.10+**
- **Embeddings:** `sentence-transformers` (`all-MiniLM-L6-v2`, local)
- **Vector database:** ChromaDB (persistent, cosine similarity)
- **LLM:** any OpenAI-compatible API — local **Ollama** or OpenAI
- **UI:** Streamlit (custom-themed)
- **PDF parsing:** pypdf

## Project Structure

```text
.
├── app.py                 # Streamlit app (Ask / Summary / Flashcards)
├── cli.py                 # Command-line Q&A
├── requirements.txt
├── .env.example
├── .streamlit/config.toml # UI theme
├── data/docs/             # Sample notes (replaceable)
└── src/
    ├── config.py          # Configuration
    ├── ingest.py          # Load / chunk / embed / store + uploads + PDF
    ├── retriever.py       # Semantic search
    ├── llm.py             # OpenAI-compatible LLM client
    └── rag.py             # Q&A, summary, flashcard generation
```

## Setup

```bash
git clone https://github.com/zelaplagg/<your-repo-name>.git
cd <your-repo-name>

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

### Run a free local model (recommended)

```bash
# Install Ollama from https://ollama.com, then:
ollama pull llama3.2
```

`.env`:

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2
```

*(Prefer OpenAI? Set `LLM_API_KEY` to your key and `LLM_MODEL=gpt-4o-mini`, and leave
`LLM_BASE_URL` empty.)*

## Usage

```bash
streamlit run app.py
```

Then, in the app:

1. Upload your notes (or click **Load sample notes**) in the sidebar.
2. Use the **Ask**, **Summary**, or **Flashcards** tab.

Command-line Q&A is also available:

```bash
python cli.py "What is overfitting and how do you fix it?"
```

## Screenshots

<!-- TODO: add screenshots of the app once you run it -->
<!-- ![Ask tab](docs/screenshot_ask.png) -->
<!-- ![Flashcards](docs/screenshot_flashcards.png) -->

## Future Work

- Highlight the exact sentence a fact came from.
- Spaced-repetition scheduling for flashcards.
- Export summaries and flashcards to PDF / Anki.

## Author

**Anastasiia Zelenska** — Computer Systems Engineering @ KPI · Business Informatics @ University of Vienna

- GitHub: [zelaplagg](https://github.com/zelaplagg)
- LinkedIn: [Anastasiia Zelenska](https://www.linkedin.com/in/anastasiia-zelenska-50404a27a)

## License

Released under the MIT License — see [LICENSE](LICENSE).

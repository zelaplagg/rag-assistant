"""StudyMate — an AI study assistant that answers questions about your own notes.

Run with:
    streamlit run app.py
"""
import streamlit as st

from src.rag import answer_question, summarize, generate_flashcards
from src.ingest import (
    add_text, ingest_sample, clear_index, count_chunks,
    list_sources,
)
from src import config
from src.loaders import extract_text

st.set_page_config(page_title="StudyMate — AI Study Assistant", page_icon="📚", layout="wide")

# ------------------------------------------------------------------ styling
st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1100px; }
      /* Hero */
      .hero {
        background: linear-gradient(120deg, #5B4BE1 0%, #8B5CF6 55%, #A855F7 100%);
        border-radius: 20px; padding: 34px 40px; color: #fff;
        box-shadow: 0 12px 30px rgba(91,75,225,0.25); margin-bottom: 22px;
      }
      .hero h1 { color:#fff; font-size: 2.1rem; margin: 0 0 6px 0; font-weight: 800; letter-spacing:-0.5px;}
      .hero p  { color: #EEE9FF; font-size: 1.05rem; margin: 0; }
      /* Feature chips under hero */
      .chips { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }
      .chip { background: rgba(255,255,255,0.18); color:#fff; padding:6px 14px;
              border-radius:999px; font-size:0.85rem; font-weight:600; }
      /* Cards */
      .card { background:#fff; border:1px solid #ECEAF6; border-radius:16px;
              padding:20px 22px; box-shadow:0 4px 14px rgba(30,34,51,0.05); }
      .empty { text-align:center; padding:46px 20px; color:#5b5f70; }
      .empty .big { font-size:3rem; margin-bottom:6px; }
      /* Buttons */
      .stButton>button { border-radius:10px; font-weight:600; }
      /* Source pill */
      .srcpill { display:inline-block; background:#F0EEFB; color:#5B4BE1;
                 padding:3px 10px; border-radius:8px; font-size:0.8rem;
                 font-weight:600; margin:2px 4px 2px 0; }
      /* Flashcard */
      .flash { background:#FBFAFF; border:1px solid #E7E3F8; border-left:5px solid #5B4BE1;
               border-radius:12px; padding:16px 18px; margin-bottom:12px; }
      .flash .q { font-weight:700; color:#1E2233; margin-bottom:2px; }
      footer, #MainMenu { visibility:hidden; }
      .credit { text-align:center; color:#9aa0af; font-size:0.85rem; margin-top:28px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ hero
st.markdown(
    """
    <div class="hero">
      <h1>📚 StudyMate</h1>
      <p>Turn your lecture notes into an interactive tutor — ask questions, get summaries, and quiz yourself.</p>
      <div class="chips">
        <span class="chip">💬 Ask your notes</span>
        <span class="chip">📝 Instant summaries</span>
        <span class="chip">🎴 Auto flashcards</span>
        <span class="chip">🔒 Runs locally</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("📁 Your notes")

    n_chunks = count_chunks()
    sources = list_sources()
    c1, c2 = st.columns(2)
    c1.metric("Notes", len(sources))
    c2.metric("Chunks", n_chunks)

    if sources:
        st.caption("Loaded files:")
        st.markdown("".join(f'<span class="srcpill">{s}</span>' for s in sources),
                    unsafe_allow_html=True)

    st.divider()
    st.subheader("➕ Add notes")
    uploads = st.file_uploader(
        "Upload .md, .txt, .pdf or .docx",
        type=["md", "txt", "pdf", "docx"],
        accept_multiple_files=True,
    )
    if st.button("Add to my notes", use_container_width=True, type="primary"):
        if not uploads:
            st.warning("Choose one or more files first.")
        else:
            added = 0
            with st.spinner("Reading and indexing your notes..."):
                for f in uploads:
                    try:
                        text = extract_text(f.name, f.read())
                        added += add_text(f.name, text)
                    except Exception as e:
                        st.error(f"{f.name}: {e}")
            st.success(f"Added {added} chunks from {len(uploads)} file(s).")
            st.rerun()

    st.caption("No files handy? Load the sample notes to try it out:")
    if st.button("Load sample notes", use_container_width=True):
        with st.spinner("Loading sample notes..."):
            ingest_sample()
        st.rerun()

    if sources and st.button("🗑️ Clear all notes", use_container_width=True):
        clear_index()
        st.session_state.pop("messages", None)
        st.rerun()

    st.divider()
    model_label = config.LLM_MODEL + (" (local)" if config.LLM_BASE_URL else "")
    st.caption(f"🧠 Model: **{model_label}**")

# ------------------------------------------------------------------ empty state
if count_chunks() == 0:
    st.markdown(
        """
        <div class="card empty">
          <div class="big">📥</div>
          <h3>Add your notes to get started</h3>
          <p>Upload your lecture notes (.md, .txt, .pdf or .docx) from the left sidebar,<br>
          or click <b>Load sample notes</b> to try StudyMate right away.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="credit">Built by Anastasiia Zelenska · RAG · embeddings · ChromaDB · local LLM</div>',
                unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------------------ main tabs
tab_ask, tab_sum, tab_quiz = st.tabs(["💬  Ask", "📝  Summary", "🎴  Flashcards"])

# --- Ask (chat) ---
with tab_ask:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask anything about your notes..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = answer_question(prompt)
            st.markdown(result.text)
            if result.passages:
                with st.expander("📎 Sources"):
                    for p in result.passages:
                        st.markdown(f'<span class="srcpill">{p.source} · {p.score}</span>',
                                    unsafe_allow_html=True)
                        st.caption(p.text[:280] + ("..." if len(p.text) > 280 else ""))
        st.session_state.messages.append({"role": "assistant", "content": result.text})

# --- Summary ---
with tab_sum:
    st.markdown("#### Summarize a topic from your notes")
    topic = st.text_input("Topic", placeholder="e.g. predictive maintenance", key="sum_topic")
    if st.button("Generate summary", type="primary", key="sum_btn"):
        if topic.strip():
            with st.spinner("Summarizing..."):
                res = summarize(topic)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(res.text)
            st.markdown("</div>", unsafe_allow_html=True)
            if res.passages:
                st.caption("Based on: " + ", ".join(sorted({p.source for p in res.passages})))
        else:
            st.warning("Enter a topic first.")

# --- Flashcards ---
with tab_quiz:
    st.markdown("#### Generate flashcards to test yourself")
    qcol1, qcol2 = st.columns([3, 1])
    q_topic = qcol1.text_input("Topic", placeholder="e.g. RAG pipeline", key="quiz_topic")
    q_n = qcol2.slider("Cards", 3, 8, 5, key="quiz_n")
    if st.button("Generate flashcards", type="primary", key="quiz_btn"):
        if q_topic.strip():
            with st.spinner("Creating flashcards..."):
                cards, passages = generate_flashcards(q_topic, q_n)
            if not cards:
                st.info("Couldn't build flashcards for that topic. Try a topic closer to your notes.")
            for i, c in enumerate(cards, 1):
                st.markdown(f'<div class="flash"><div class="q">Q{i}. {c.question}</div></div>',
                            unsafe_allow_html=True)
                with st.expander("Show answer"):
                    st.markdown(c.answer)
        else:
            st.warning("Enter a topic first.")

st.markdown('<div class="credit">Built by Anastasiia Zelenska · RAG · embeddings · ChromaDB · local LLM</div>',
            unsafe_allow_html=True)

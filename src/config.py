"""Central configuration, loaded from environment variables (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM (OpenAI-compatible endpoint)
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None          # None -> OpenAI default
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Embeddings (local sentence-transformers model)
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# Paths
DOCS_DIR = os.getenv("DOCS_DIR", "data/docs")
CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base")

# Chunking / retrieval
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("TOP_K", "4"))

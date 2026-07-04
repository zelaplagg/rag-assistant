# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation (RAG) is a technique that improves the answers of a
large language model (LLM) by giving it relevant external information at query time,
instead of relying only on what the model memorized during training.

## Why RAG is useful

- **Reduces hallucination:** the model answers from retrieved passages, so it is
  grounded in real source documents.
- **Keeps knowledge current:** you can update the document store without retraining
  the model.
- **Adds private knowledge:** the model can answer about internal documents it was
  never trained on.

## How a RAG pipeline works

1. **Ingestion:** documents are split into smaller chunks.
2. **Embedding:** each chunk is converted into a numeric vector that captures its
   meaning, using an embedding model.
3. **Indexing:** the vectors are stored in a vector database.
4. **Retrieval:** when a user asks a question, the question is embedded and the most
   similar chunks are retrieved using a similarity metric such as cosine similarity.
5. **Generation:** the retrieved chunks are inserted into the prompt, and the LLM
   generates an answer grounded in that context, ideally citing its sources.

## Key components

- **Embedding model:** turns text into vectors (e.g. sentence-transformers models).
- **Vector database:** stores and searches embeddings efficiently (e.g. Chroma,
  FAISS, Pinecone).
- **Chunking strategy:** controls how documents are split; chunk size and overlap
  affect retrieval quality.
- **Top-k:** the number of passages retrieved for each question.

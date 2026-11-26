FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    STUDYMATE_PUBLIC=1 STUDYMATE_MODEL_CACHE=/opt/studymate-model \
    TOKENIZERS_PARALLELISM=false RAYON_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
WORKDIR /app
COPY requirements-production.txt api.py ./
COPY src/ src/
COPY data/docs/ data/docs/
COPY --from=frontend /build/dist/studymate/browser/ frontend/dist/studymate/browser/
# Chroma verifies the model archive checksum. Bake the verified model into the image.
RUN groupadd --gid 10001 studymate \
    && useradd --uid 10001 --gid studymate --no-create-home studymate \
    && pip install --no-cache-dir -r requirements-production.txt \
    && python -c 'from src.web_sessions import web_embedder; web_embedder()(["StudyMate"])' \
    && rm -f "$STUDYMATE_MODEL_CACHE/onnx.tar.gz" \
    && chmod -R a+rX /app "$STUDYMATE_MODEL_CACHE"
USER studymate
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=4s --start-period=45s \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.getenv("PORT", "10000") + "/api/health", timeout=3)' || exit 1
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --no-access-log --no-server-header --timeout-keep-alive 5"]

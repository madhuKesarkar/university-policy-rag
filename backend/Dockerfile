# Production image for the FastAPI backend. Deliberately does NOT include the ingestion
# pipeline's heavy deps (Docling, torch's larger friends via OCR, etc.) — see requirements-prod.txt.
FROM python:3.12-slim

WORKDIR /app

COPY requirements-prod.txt .
# --extra-index-url pins torch to the CPU-only wheel (~200MB) instead of the default CUDA
# build (~2GB+) — this container never touches a GPU, and the size difference is the
# difference between fitting a free-tier host's disk/memory and not.
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements-prod.txt

COPY app ./app
COPY ingestion/__init__.py ingestion/embed.py ./ingestion/

ENV PORT=8000
EXPOSE 8000

# Pre-download the embedding + reranker models at build time, not on the first live request —
# without this, the container's first request after every cold start pays a multi-minute
# model-download tax (as we hit repeatedly in local dev) instead of a few hundred ms.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('BAAI/bge-small-en-v1.5'); \
    CrossEncoder('BAAI/bge-reranker-base')"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

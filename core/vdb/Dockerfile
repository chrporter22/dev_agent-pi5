# ==========================
# Dockerfile: openclaw-vdb
# ==========================

# Base image: lightweight Python ARM64
FROM python:3.12-slim-bullseye

# --------------------------
# Metadata
# --------------------------
LABEL maintainer="Christian Porter <cporter1993@gmail.com>"
LABEL description="Vector Database container on Pi5. FAISS + SQLite + ARM64 embeddings."

# --------------------------
# Environment
# --------------------------
ENV PYTHONUNBUFFERED=1 \
    FAISS_ENABLE_PYTHON=1 \
    VDB_DATA_DIR=/data \
    VDB_API_PORT=8081

WORKDIR /app

# --------------------------
# System Dependencies
# --------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    wget \
    git \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# --------------------------
# Python Dependencies
# --------------------------
# FAISS ARM64 CPU, SQLite, FastAPI + Uvicorn
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        faiss-cpu \
        sqlite-utils \
        fastapi[all] \
        uvicorn[standard] \
        numpy \
        pydantic \
        python-multipart \
        python-dotenv \
        sentence-transformers \
        transformers \
        torch==2.2.0+cpu -f https://download.pytorch.org/whl/cpu/torch_stable.html

# --------------------------
# Copy VDB Source Code
# --------------------------
COPY ./vdb/ /app/

# Ensure /data exists and is writable
RUN mkdir -p $VDB_DATA_DIR && chown -R 1000:1000 $VDB_DATA_DIR

# --------------------------
# Expose API port
# --------------------------
EXPOSE $VDB_API_PORT

# --------------------------
# Non-root user
# --------------------------
RUN useradd --create-home --uid 1000 vdbuser
USER vdbuser

# --------------------------
# Entrypoint
# --------------------------
# Starts FastAPI Uvicorn server on 0.0.0.0:8081
CMD ["uvicorn", "vdb:app", "--host", "0.0.0.0", "--port", "8081", "--reload"]

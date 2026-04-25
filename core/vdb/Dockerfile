# ==========================
# Dockerfile: openclaw-vdb (FIXED)
# ==========================

FROM python:3.12-slim-bullseye

# --------------------------
# Metadata
# --------------------------
LABEL maintainer="Christian Porter <cporter1993@gmail.com>"
LABEL description="OpenClaw VDB - internal vector + SQLite + FAISS service (ARM64)"

# --------------------------
# Environment
# --------------------------
ENV PYTHONUNBUFFERED=1 \
    VDB_DATA_DIR=/data \
    VDB_API_PORT=8081 \
    FAISS_ENABLE_PYTHON=1

WORKDIR /app

# --------------------------
# System dependencies
# --------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libsqlite3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --------------------------
# Python dependencies
# --------------------------
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        faiss-cpu \
        numpy \
        pydantic \
        python-multipart \
        python-dotenv \
        sqlite-utils \
        sentence-transformers \
        transformers

# NOTE:
# torch is optional depending on your embedding strategy
# (keep it OUT unless you actually use local transformer inference)

# --------------------------
# Copy source
# --------------------------
COPY ./app /app/app
COPY ./bootstrap /app/bootstrap

# --------------------------
# Create data directory FIRST
# --------------------------
RUN mkdir -p /data

# --------------------------
# Create non-root user
# --------------------------
RUN useradd -m -u 1000 vdbuser && \
    chown -R vdbuser:vdbuser /app && \
    chown -R vdbuser:vdbuser /data

USER vdbuser

# --------------------------
# IMPORTANT: internal-only service
# --------------------------
EXPOSE 8081

# --------------------------
# Entrypoint (FIXED PATH)
# --------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]

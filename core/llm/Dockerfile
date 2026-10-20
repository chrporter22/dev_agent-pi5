# core/llm/Dockerfile
# ---------------------------
# THIN FLASK PROXY → EXTERNAL LITELLM GATEWAY
# ---------------------------
FROM python:3.12-slim

# ---------------------------
# CREATE NON-ROOT USER
# ---------------------------
RUN groupadd --system llmgroup \
    && useradd --system --gid llmgroup --home /app --shell /sbin/nologin llmuser

# ---------------------------
# APP DIRECTORY
# ---------------------------
WORKDIR /app

# ---------------------------
# PYTHON DEPENDENCIES (CACHED LAYER)
# ---------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------
# APP CODE
# ---------------------------
COPY app.py .
COPY config.py .

RUN chown -R llmuser:llmgroup /app

# ---------------------------
# RUNTIME
# ---------------------------
USER llmuser
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ---------------------------
# INTERNAL SERVICE PORT ONLY
# ---------------------------
EXPOSE 8080

# ---------------------------
# ENTRYPOINT
# ---------------------------
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

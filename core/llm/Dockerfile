FROM ubuntu:22.04

# ---- Create non-root user early ----
RUN useradd -ms /bin/bash llmuser

# ---- Install system dependencies ----
USER root
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ---- Build llama.cpp (ARM64 optimized) ----
WORKDIR /home/llmuser

RUN git clone https://github.com/ggerganov/llama.cpp.git \
    && cd llama.cpp \
    && make LLAMA_NATIVE=1

# ---- VERIFY server binary exists (fails build if not) ----
RUN test -f /home/llmuser/llama.cpp/server

# ---- Create model directory ----
RUN mkdir -p /models

# ---- Fix ownership for non-root execution ----
RUN chown -R llmuser:llmuser /home/llmuser \
    && chown -R llmuser:llmuser /models

# ---- Switch to non-root ----
USER llmuser

# ---- Copy Flask wrapper ----
WORKDIR /home/llmuser
COPY --chown=llmuser:llmuser ./llm-server ./llm-server
WORKDIR /home/llmuser/llm-server

EXPOSE 8080

ENTRYPOINT ["./start-llm.sh"]

FROM ubuntu:22.04

# ---------------------------
# CREATE NON-ROOT USER
# ---------------------------
RUN useradd -ms /bin/bash llmuser

USER root

# ---------------------------
# SYSTEM DEPENDENCIES
# ---------------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------
# BUILD llama.cpp (REPRODUCIBLE)
# ---------------------------
WORKDIR /home/llmuser

RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git \
    && cd llama.cpp \
    && make -j$(nproc) LLAMA_NATIVE=1

# ---------------------------
# VERIFY BUILD OUTPUT SAFELY
# ---------------------------
RUN find /home/llmuser/llama.cpp -name server || true

# ---------------------------
# MODEL DIRECTORY
# ---------------------------
RUN mkdir -p /models

# ---------------------------
# OWNERSHIP FIX
# ---------------------------
RUN chown -R llmuser:llmuser /home/llmuser \
    && chown -R llmuser:llmuser /models

# ---------------------------
# SWITCH TO NON-ROOT
# ---------------------------
USER llmuser

# ---------------------------
# WRAPPER APP
# ---------------------------
WORKDIR /home/llmuser
COPY --chown=llmuser:llmuser ./llm-server ./llm-server

WORKDIR /home/llmuser/llm-server

# ---------------------------
# INTERNAL SERVICE PORT ONLY
# ---------------------------
EXPOSE 8080

# ---------------------------
# ENTRYPOINT
# ---------------------------
ENTRYPOINT ["./start-llm.sh"]

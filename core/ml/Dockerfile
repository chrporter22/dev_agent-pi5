# /core/ml/Dockerfile

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN useradd -ms /bin/bash mluser

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/models
RUN mkdir -p /app/data

RUN chown -R mluser:mluser /app

USER mluser

CMD ["python", "ml_worker.py"]

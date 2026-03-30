FROM python:3.11-alpine

RUN addgroup -S botgroup && adduser -S botuser -G botgroup

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER botuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]

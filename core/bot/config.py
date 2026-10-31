import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER = int(os.getenv("ALLOWED_USER", "0"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

REDIS_USER = os.getenv("REDIS_USER", "bot")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL")
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY")
AI_GATEWAY_MODEL = os.getenv("AI_GATEWAY_MODEL", "gpt-4o-mini")

CHAT_HISTORY_MAX_TURNS = int(os.getenv("CHAT_HISTORY_MAX_TURNS", "20"))
TELEGRAM_MAX_CHARS = int(os.getenv("TELEGRAM_MAX_CHARS", "3800"))

DEFAULT_REPO = os.getenv("DEFAULT_REPO")
SANDBOX_DIR = os.getenv("SANDBOX_DIR", "/sandbox")

RATE_LIMIT = 10
RATE_WINDOW = 60


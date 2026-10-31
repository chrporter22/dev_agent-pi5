import json
from typing import List, Optional

import redis

from config import (
    CHAT_HISTORY_MAX_TURNS,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_USER
)

# ============================================================================
# CHAT STORE — core/bot/chat_store.py
# Redis-backed per-chat history and per-chat model override.
# Public API: ChatStore.append / history / clear / get_model / set_model.
# ============================================================================


def _history_key(chat_id) -> str:
    return f"chat:history:{chat_id}"


def _model_key(chat_id) -> str:
    return f"chat:model:{chat_id}"


# ----------------------------------
# PUBLIC API
# ----------------------------------
class ChatStore:
    def __init__(self, client: Optional[redis.Redis] = None):
        if client is None:
            self._r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                username=REDIS_USER,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
        else:
            self._r = client

    def append(self, chat_id, role: str, content: str) -> None:
        key = _history_key(chat_id)
        turn = json.dumps({"role": role, "content": content})
        pipe = self._r.pipeline()
        pipe.rpush(key, turn)
        pipe.ltrim(key, -CHAT_HISTORY_MAX_TURNS, -1)
        pipe.execute()

    def history(self, chat_id) -> List[dict]:
        raw = self._r.lrange(_history_key(chat_id), 0, -1)
        return [json.loads(turn) for turn in raw]

    def clear(self, chat_id) -> None:
        self._r.delete(_history_key(chat_id))

    def get_model(self, chat_id) -> Optional[str]:
        return self._r.get(_model_key(chat_id))

    def set_model(self, chat_id, model: str) -> None:
        self._r.set(_model_key(chat_id), model)

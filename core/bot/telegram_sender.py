import re
from typing import List

import requests

from config import TELEGRAM_MAX_CHARS, TELEGRAM_TOKEN

# ============================================================================
# TELEGRAM SENDER — core/bot/telegram_sender.py
# Sends long replies in chunks that fit Telegram's message size limit.
# Public API: _chunk_send(chat_id, text).
# ============================================================================

BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ----------------------------------
# PRIVATE HELPERS
# ----------------------------------
def _send(chat_id, text: str) -> None:
    requests.post(
        f"{BASE}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


def _hard_split(block: str, limit: int) -> List[str]:
    lines = block.split("\n")
    out: List[str] = []
    buf = ""

    for line in lines:
        candidate = f"{buf}\n{line}" if buf else line

        if len(candidate) <= limit:
            buf = candidate
        else:
            if buf:
                out.append(buf)

            if len(line) > limit:
                for i in range(0, len(line), limit):
                    out.append(line[i:i + limit])
                buf = ""
            else:
                buf = line

    if buf:
        out.append(buf)

    return out


# ----------------------------------
# PUBLIC API
# ----------------------------------
def _chunk_send(chat_id, text: str) -> None:
    if len(text) <= TELEGRAM_MAX_CHARS:
        _send(chat_id, text)
        return

    blocks = re.split(r"\n\n+", text)

    chunks: List[str] = []
    current = ""

    for block in blocks:
        if len(block) > TELEGRAM_MAX_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(block, TELEGRAM_MAX_CHARS))
            continue

        separator = "\n\n" if current else ""
        candidate = f"{current}{separator}{block}"

        if len(candidate) <= TELEGRAM_MAX_CHARS:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = block

    if current:
        chunks.append(current)

    for chunk in chunks:
        _send(chat_id, chunk)

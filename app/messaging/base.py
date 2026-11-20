from typing import Protocol

from app.models import Reply

MAX_MESSAGE_CHARS = 4000  # Telegram allows 4096, WhatsApp 4096


class Messenger(Protocol):
    async def send(self, user_id: str, reply: Reply) -> None: ...


def split_text(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split long replies on paragraph boundaries so each part fits one message."""
    parts: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            parts.append(current)
        while len(para) > limit:
            parts.append(para[:limit])
            para = para[limit:]
        current = para
    if current:
        parts.append(current)
    return parts

"""Telegram Bot API: used for early testing before WhatsApp access is approved."""

import httpx

from app.messaging.base import split_text
from app.models import IncomingMessage, Media, Reply

API = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str, http: httpx.AsyncClient):
        self._token = token
        self._http = http

    def _url(self, method: str) -> str:
        return f"{API}/bot{self._token}/{method}"

    async def download(self, file_id: str) -> bytes:
        r = await self._http.get(self._url("getFile"), params={"file_id": file_id})
        r.raise_for_status()
        path = r.json()["result"]["file_path"]
        f = await self._http.get(f"{API}/file/bot{self._token}/{path}")
        f.raise_for_status()
        return f.content

    async def parse_update(self, update: dict) -> IncomingMessage | None:
        msg = update.get("message")
        if not msg or "chat" not in msg:
            return None
        incoming = IncomingMessage(
            channel="telegram",
            message_id=str(update.get("update_id", msg.get("message_id"))),
            user_id=str(msg["chat"]["id"]),
            text=msg.get("text") or msg.get("caption") or "",
        )
        if msg.get("photo"):
            largest = msg["photo"][-1]  # Telegram lists sizes smallest first
            incoming.image = Media(await self.download(largest["file_id"]), "image/jpeg")
        elif msg.get("document", {}).get("mime_type", "").startswith("image/"):
            doc = msg["document"]
            incoming.image = Media(await self.download(doc["file_id"]), doc["mime_type"])
        elif msg.get("voice") or msg.get("audio"):
            audio = msg.get("voice") or msg.get("audio")
            mime = audio.get("mime_type", "audio/ogg")
            incoming.audio = Media(await self.download(audio["file_id"]), mime)
        return incoming

    async def send(self, user_id: str, reply: Reply) -> None:
        for part in split_text(reply.text):
            r = await self._http.post(
                self._url("sendMessage"), json={"chat_id": user_id, "text": part}
            )
            r.raise_for_status()
        if reply.audio:
            r = await self._http.post(
                self._url("sendVoice"),
                data={"chat_id": user_id},
                files={"voice": ("reply.ogg", reply.audio.data, reply.audio.mime_type)},
            )
            r.raise_for_status()

"""WhatsApp Cloud API: receive webhooks, download media, send replies."""

import hashlib
import hmac

import httpx

from app.messaging.base import split_text
from app.models import IncomingMessage, Media, Reply

GRAPH = "https://graph.facebook.com"


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256 header (HMAC-SHA256 of the raw body)."""
    if not app_secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


def extract_messages(payload: dict) -> list[dict]:
    """Pull message objects out of a webhook payload (ignores delivery/read statuses)."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            out.extend(change.get("value", {}).get("messages", []))
    return out


class WhatsAppClient:
    def __init__(
        self, access_token: str, phone_number_id: str, api_version: str, http: httpx.AsyncClient
    ):
        self._token = access_token
        self._phone_id = phone_number_id
        self._version = api_version
        self._http = http

    @property
    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def download(self, media_id: str) -> Media:
        meta = await self._http.get(f"{GRAPH}/{self._version}/{media_id}", headers=self._auth)
        meta.raise_for_status()
        info = meta.json()
        f = await self._http.get(info["url"], headers=self._auth)
        f.raise_for_status()
        return Media(f.content, info.get("mime_type", "application/octet-stream"))

    async def parse_message(self, msg: dict) -> IncomingMessage | None:
        kind = msg.get("type")
        incoming = IncomingMessage(channel="whatsapp", message_id=msg["id"], user_id=msg["from"])
        if kind == "text":
            incoming.text = msg["text"]["body"]
        elif kind == "image":
            incoming.text = msg["image"].get("caption", "")
            incoming.image = await self.download(msg["image"]["id"])
        elif kind == "audio":
            incoming.audio = await self.download(msg["audio"]["id"])
        # Other types (stickers, location, ...) arrive with no content → "unsupported" reply.
        return incoming

    async def send(self, user_id: str, reply: Reply) -> None:
        url = f"{GRAPH}/{self._version}/{self._phone_id}/messages"
        for part in split_text(reply.text):
            r = await self._http.post(
                url,
                headers=self._auth,
                json={
                    "messaging_product": "whatsapp",
                    "to": user_id,
                    "type": "text",
                    "text": {"body": part},
                },
            )
            r.raise_for_status()
        # Voice replies need a media upload step; add it once a TTS provider is chosen.

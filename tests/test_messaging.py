import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.messaging.base import split_text
from app.messaging.whatsapp import extract_messages, verify_signature


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_whatsapp_signature():
    body = b'{"a":1}'
    assert verify_signature("s3cret", body, sign("s3cret", body))
    assert not verify_signature("s3cret", body, sign("other", body))
    assert not verify_signature("s3cret", body, None)
    assert not verify_signature("", body, sign("", body))


def test_extract_messages_ignores_statuses():
    payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"messages": [{"id": "m1", "from": "91", "type": "text"}]}},
                    {"value": {"statuses": [{"id": "m0", "status": "read"}]}},
                ]
            }
        ]
    }
    assert [m["id"] for m in extract_messages(payload)] == ["m1"]


def test_split_text():
    text = "\n\n".join(["a" * 30] * 5)
    parts = split_text(text, limit=70)
    assert all(len(p) <= 70 for p in parts)
    assert "".join(parts).replace("\n", "") == "a" * 150


def test_webhooks_reject_bad_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cret")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-secret")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as client:
        r = client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "42",
            },
        )
        assert r.status_code == 200 and r.text == "42"
        assert (
            client.get(
                "/webhook/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong",
                    "hub.challenge": "42",
                },
            ).status_code
            == 403
        )

        body = json.dumps({"entry": []}).encode()
        assert client.post("/webhook/whatsapp", content=body).status_code == 403
        ok = client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": sign("s3cret", body)},
        )
        assert ok.status_code == 200

        assert client.post("/webhook/telegram", json={}).status_code == 403
        assert client.get("/health").json()["status"] == "ok"
    get_settings.cache_clear()

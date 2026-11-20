"""FastAPI entrypoint: webhooks only. Logic lives in app/pipeline.py."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import Settings, get_settings
from app.llm.client import ClaudeLLM
from app.messaging.base import Messenger
from app.messaging.telegram import TelegramClient
from app.messaging.whatsapp import WhatsAppClient, extract_messages, verify_signature
from app.models import IncomingMessage
from app.pipeline import Pipeline
from app.rag.retriever import Retriever
from app.speech.base import get_speech_provider
from app.store import Store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def build_pipeline(settings: Settings) -> Pipeline:
    return Pipeline(
        settings=settings,
        llm=ClaudeLLM(settings.llm_model, settings.anthropic_api_key),
        retriever=Retriever(str(settings.chroma_dir), settings.collection_name),
        store=Store(settings.db_path, settings.user_id_salt),
        speech=get_speech_provider(settings.speech_provider),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    http = httpx.AsyncClient(timeout=30)
    app.state.settings = settings
    app.state.pipeline = build_pipeline(settings)
    app.state.telegram = TelegramClient(settings.telegram_bot_token, http)
    app.state.whatsapp = WhatsAppClient(
        settings.whatsapp_access_token,
        settings.whatsapp_phone_number_id,
        settings.whatsapp_api_version,
        http,
    )
    yield
    await http.aclose()


app = FastAPI(title="Farmer Assistant", lifespan=lifespan)


async def process(pipeline: Pipeline, messenger: Messenger, msg: IncomingMessage) -> None:
    for reply in await pipeline.handle(msg):
        await messenger.send(msg.user_id, reply)


async def _safe(coro) -> None:
    try:
        await coro
    except Exception:
        log.exception("Background message processing failed")


@app.get("/health")
async def health(request: Request) -> dict:
    return {"status": "ok", "sources_indexed": request.app.state.pipeline.retriever.count()}


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    settings: Settings = request.app.state.settings
    if not settings.telegram_webhook_secret or secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403)
    update = await request.json()
    pipeline: Pipeline = request.app.state.pipeline
    if not pipeline.store.mark_processed("telegram", str(update.get("update_id"))):
        return {"ok": True}  # duplicate delivery

    async def run() -> None:
        msg = await request.app.state.telegram.parse_update(update)
        if msg:
            await process(pipeline, request.app.state.telegram, msg)

    background.add_task(_safe, run())
    return {"ok": True}


@app.get("/webhook/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(
    request: Request,
    mode: str = Query(alias="hub.mode", default=""),
    token: str = Query(alias="hub.verify_token", default=""),
    challenge: str = Query(alias="hub.challenge", default=""),
) -> str:
    settings: Settings = request.app.state.settings
    if (
        mode == "subscribe"
        and settings.whatsapp_verify_token
        and token == settings.whatsapp_verify_token
    ):
        return challenge
    raise HTTPException(status_code=403)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks) -> dict:
    settings: Settings = request.app.state.settings
    body = await request.body()
    if not verify_signature(
        settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")
    ):
        raise HTTPException(status_code=403)
    client: WhatsAppClient = request.app.state.whatsapp
    pipeline: Pipeline = request.app.state.pipeline

    for raw in extract_messages(await request.json()):
        # WhatsApp retries slow or failed deliveries; handle each message id once.
        if not pipeline.store.mark_processed("whatsapp", raw["id"]):
            continue

        async def run(raw: dict = raw) -> None:
            msg = await client.parse_message(raw)
            if msg:
                await process(pipeline, client, msg)

        background.add_task(_safe, run())
    return {"ok": True}

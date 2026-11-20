"""Run the bot against Telegram with long polling. No public URL or webhook needed.

Create a bot with @BotFather, put the token in TELEGRAM_BOT_TOKEN, then run this.
"""

import asyncio
import logging

import _bootstrap  # noqa: F401
import httpx

from app.config import get_settings
from app.main import build_pipeline, process
from app.messaging.telegram import TelegramClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram_polling")


async def main() -> None:
    s = get_settings()
    if not s.telegram_bot_token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
    pipeline = build_pipeline(s)
    async with httpx.AsyncClient(timeout=60) as http:
        tg = TelegramClient(s.telegram_bot_token, http)
        base = f"https://api.telegram.org/bot{s.telegram_bot_token}"
        await http.post(f"{base}/deleteWebhook")  # polling and webhooks can't both be active
        offset = 0
        log.info("Polling Telegram. Send your bot a message.")
        while True:
            try:
                r = await http.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 50})
                r.raise_for_status()
                updates = r.json()["result"]
            except httpx.HTTPError as e:
                log.warning("Polling failed: %s", e)
                await asyncio.sleep(5)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                if not pipeline.store.mark_processed("telegram", str(update["update_id"])):
                    continue
                try:
                    msg = await tg.parse_update(update)
                    if msg:
                        await process(pipeline, tg, msg)
                except Exception:
                    log.exception("Failed to handle update %s", update["update_id"])


if __name__ == "__main__":
    asyncio.run(main())

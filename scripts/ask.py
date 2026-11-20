"""Ask the assistant from the terminal, without any messaging setup.

python scripts/ask.py "my chilli leaves are curling upwards"
python scripts/ask.py --image leaf.jpg "what is this?"
"""

import argparse
import asyncio
import mimetypes
from pathlib import Path

import _bootstrap  # noqa: F401

from app.config import get_settings
from app.main import build_pipeline
from app.models import IncomingMessage, Media


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default="")
    parser.add_argument("--image", type=Path)
    args = parser.parse_args()

    pipeline = build_pipeline(get_settings())
    user = "cli-user"
    # Skip the consent prompt for local testing.
    pipeline.store.set_consent(pipeline.store.user_hash("cli", user), "yes")

    msg = IncomingMessage(channel="cli", message_id="cli", user_id=user, text=args.question)
    if args.image:
        mime = mimetypes.guess_type(args.image.name)[0] or "image/jpeg"
        msg.image = Media(args.image.read_bytes(), mime)

    for reply in await pipeline.handle(msg):
        print(reply.text, end="\n\n")
    record = pipeline.store.interactions()[-1]
    print(f"[confidence={record['confidence'] or '-'} fallback={record['fallback_reason'] or '-'}]")


if __name__ == "__main__":
    asyncio.run(main())

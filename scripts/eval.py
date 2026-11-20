"""Run data/eval/questions.jsonl through the pipeline and write a CSV for expert review."""

import asyncio
import csv
import json
import mimetypes
from datetime import datetime

import _bootstrap  # noqa: F401

from app.config import ROOT, get_settings
from app.main import build_pipeline
from app.models import IncomingMessage, Media

EVAL_DIR = ROOT / "data" / "eval"


async def main() -> None:
    lines = (EVAL_DIR / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    if not cases:
        raise SystemExit("data/eval/questions.jsonl is empty. See data/eval/README.md.")

    pipeline = build_pipeline(get_settings())
    rows = []
    for case in cases:
        user = f"eval-{case['id']}"
        pipeline.store.set_consent(pipeline.store.user_hash("cli", user), "yes")
        msg = IncomingMessage(
            channel="cli", message_id=case["id"], user_id=user, text=case.get("question", "")
        )
        if case.get("image"):
            path = ROOT / case["image"]
            msg.image = Media(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/jpeg")
        replies = await pipeline.handle(msg)
        record = pipeline.store.interactions()[-1]
        got = "fallback" if record["fallback_reason"] else "answer"
        rows.append(
            {
                "id": case["id"],
                "question": case.get("question", ""),
                "expect": case.get("expect", ""),
                "got": got,
                "match": got == case.get("expect", got),
                "confidence": record["confidence"],
                "fallback_reason": record["fallback_reason"],
                "answer": "\n\n".join(r.text for r in replies),
                "expert_verdict": "",
                "expert_notes": "",
            }
        )
        print(f"{case['id']}: expect={case.get('expect')} got={got} {record['fallback_reason']}")

    out = EVAL_DIR / f"results-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    matched = sum(r["match"] for r in rows)
    print(f"\n{matched}/{len(rows)} matched expected behaviour. Review: {out}")


if __name__ == "__main__":
    asyncio.run(main())

"""Crop problem diagnosis from a photo. Diagnosis only, never treatment (CLAUDE.md §3)."""

import base64

from app.config import Settings
from app.llm.client import LLM
from app.llm.prompts import VISION_SYSTEM, fmt
from app.llm.schemas import Diagnosis
from app.models import Media

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def diagnose(llm: LLM, settings: Settings, image: Media, caption: str = "") -> Diagnosis:
    mime = image.mime_type if image.mime_type in SUPPORTED_IMAGE_TYPES else "image/jpeg"
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": base64.standard_b64encode(image.data).decode("ascii"),
            },
        },
        {
            "type": "text",
            "text": f"Target crop: {settings.crop}. Farmer's note: {caption or '(none)'}",
        },
    ]
    return await llm.parse(fmt(VISION_SYSTEM, settings), content, Diagnosis, effort="medium")


def diagnosis_summary(d: Diagnosis) -> str:
    return (
        f"Most likely: {d.likely_condition} (confidence: {d.confidence}). "
        f"Alternatives: {', '.join(d.alternatives) or 'none'}. "
        f"Visible symptoms: {', '.join(d.visible_symptoms) or 'not described'}."
    )

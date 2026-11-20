"""Speech-to-text / text-to-speech interface.

The provider is an open Phase 0 decision (CLAUDE.md §2). Implement `SpeechProvider`
for the chosen service and register it in `get_speech_provider`.
"""

from typing import Protocol

from app.models import Media


class SpeechProvider(Protocol):
    async def transcribe(self, audio: Media, language_code: str) -> str | None: ...

    async def synthesize(self, text: str, language_code: str) -> Media | None: ...


class NullSpeech:
    """Used until a provider is chosen: voice notes get a 'please type' reply."""

    async def transcribe(self, audio: Media, language_code: str) -> str | None:
        return None

    async def synthesize(self, text: str, language_code: str) -> Media | None:
        return None


def get_speech_provider(name: str) -> SpeechProvider:
    if name == "none":
        return NullSpeech()
    raise ValueError(f"Unknown SPEECH_PROVIDER {name!r}. Implement it in app/speech/.")

"""LLM clients. Every call returns a validated Pydantic object or raises LLMUnavailable.

Two providers are supported (LLM_PROVIDER): "gemini" (Google) and "claude" (Anthropic).
Callers pass provider-neutral content: a string, or a list of strings and Media images.
"""

import base64
import logging
from typing import Protocol, TypeVar

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.models import Media

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Content = str | list[str | Media]


class LLMUnavailable(Exception):
    """The model refused, ran out of tokens, or the API failed. Callers fall back to an expert."""


class LLM(Protocol):
    model: str

    async def parse(
        self,
        system: str,
        content: Content,
        output_type: type[T],
        effort: str = "medium",
        max_tokens: int = 8000,
    ) -> T: ...


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "gemini":
        return GeminiLLM(settings.gemini_model, settings.gemini_api_key)
    if settings.llm_provider == "claude":
        return ClaudeLLM(settings.llm_model, settings.anthropic_api_key)
    raise ValueError(f"Unknown LLM_PROVIDER {settings.llm_provider!r} (use gemini or claude)")


class GeminiLLM:
    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        self._api_key = api_key
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        # Created on first use: the SDK raises without a key, and the server should still start.
        # Empty key → SDK reads GEMINI_API_KEY / GOOGLE_API_KEY from the environment.
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key or None)
        return self._client

    @staticmethod
    def to_parts(content: Content) -> list[str | genai_types.Part]:
        items = [content] if isinstance(content, str) else content
        return [
            (
                genai_types.Part.from_bytes(data=item.data, mime_type=item.mime_type)
                if isinstance(item, Media)
                else item
            )
            for item in items
        ]

    async def parse(
        self,
        system: str,
        content: Content,
        output_type: type[T],
        effort: str = "medium",  # Gemini uses its default thinking; kept for the interface
        max_tokens: int = 8000,
    ) -> T:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=self.to_parts(content),
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=output_type,
                ),
            )
        except genai_errors.ClientError as e:
            if e.code == 404:
                log.error("Gemini model %r not found; check GEMINI_MODEL", self.model)
            raise LLMUnavailable(f"API error {e.code}") from e
        except genai_errors.APIError as e:
            raise LLMUnavailable(f"API error {e.code}") from e
        except ValueError as e:  # e.g. no API key configured
            raise LLMUnavailable(str(e)) from e

        feedback = response.prompt_feedback
        if feedback and feedback.block_reason:
            raise LLMUnavailable(f"blocked: {feedback.block_reason}")
        if isinstance(response.parsed, output_type):
            return response.parsed
        try:
            return output_type.model_validate_json(response.text or "")
        except ValidationError as e:
            reason = response.candidates[0].finish_reason if response.candidates else None
            raise LLMUnavailable(f"no structured output (finish_reason={reason})") from e


class ClaudeLLM:
    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        # Empty key → SDK resolves credentials from the environment / `ant auth login`.
        self._client = anthropic.AsyncAnthropic(api_key=api_key or None)

    @staticmethod
    def to_blocks(content: Content) -> str | list[dict]:
        if isinstance(content, str):
            return content
        blocks: list[dict] = []
        for item in content:
            if isinstance(item, Media):
                data = base64.standard_b64encode(item.data).decode("ascii")
                blocks.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": item.mime_type, "data": data},
                    }
                )
            else:
                blocks.append({"type": "text", "text": item})
        return blocks

    async def parse(
        self,
        system: str,
        content: Content,
        output_type: type[T],
        effort: str = "medium",
        max_tokens: int = 8000,
    ) -> T:
        try:
            response = await self._client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": self.to_blocks(content)}],
                output_format=output_type,
                output_config={"effort": effort},
                # On a safety-classifier decline, retry server-side on Anthropic's
                # recommended fallback model instead of failing the farmer's request.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise LLMUnavailable("rate limited") from e
        except anthropic.APIStatusError as e:
            raise LLMUnavailable(f"API error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise LLMUnavailable("connection error") from e

        if response.stop_reason == "refusal":
            raise LLMUnavailable("refusal")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise LLMUnavailable(f"no structured output (stop_reason={response.stop_reason})")
        return response.parsed_output

"""Thin wrapper around the Anthropic SDK. Every call returns a validated Pydantic object."""

from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """The model refused, ran out of tokens, or the API failed. Callers fall back to an expert."""


class LLM(Protocol):
    model: str

    async def parse(
        self,
        system: str,
        content: list[dict] | str,
        output_type: type[T],
        effort: str = "medium",
        max_tokens: int = 8000,
    ) -> T: ...


class ClaudeLLM:
    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        # Empty key → SDK resolves credentials from the environment / `ant auth login`.
        self._client = anthropic.AsyncAnthropic(api_key=api_key or None)

    async def parse(
        self,
        system: str,
        content: list[dict] | str,
        output_type: type[T],
        effort: str = "medium",
        max_tokens: int = 8000,
    ) -> T:
        try:
            response = await self._client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
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

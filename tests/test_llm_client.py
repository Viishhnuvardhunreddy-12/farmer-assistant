from types import SimpleNamespace

import pytest
from google.genai import types as genai_types

from app.config import Settings
from app.llm.client import ClaudeLLM, GeminiLLM, LLMUnavailable, build_llm
from app.llm.schemas import Understanding
from app.models import Media


def test_build_llm_picks_provider():
    assert isinstance(build_llm(Settings(_env_file=None, llm_provider="gemini")), GeminiLLM)
    assert isinstance(
        build_llm(Settings(_env_file=None, llm_provider="claude", anthropic_api_key="x")),
        ClaudeLLM,
    )
    with pytest.raises(ValueError):
        build_llm(Settings(_env_file=None, llm_provider="other"))


def test_content_conversion_for_both_providers():
    content = [Media(b"\xff\xd8", "image/jpeg"), "what is this?"]
    gemini = GeminiLLM.to_parts(content)
    assert isinstance(gemini[0], genai_types.Part) and gemini[1] == "what is this?"
    claude = ClaudeLLM.to_blocks(content)
    assert claude[0]["type"] == "image" and claude[1] == {"type": "text", "text": "what is this?"}
    assert GeminiLLM.to_parts("hi") == ["hi"]


class FakeModels:
    def __init__(self, response):
        self.response = response

    async def generate_content(self, **kwargs):
        return self.response


def gemini_with(response) -> GeminiLLM:
    llm = GeminiLLM("test-model", api_key="test-key")
    llm._client = SimpleNamespace(aio=SimpleNamespace(models=FakeModels(response)))
    return llm


async def test_gemini_returns_parsed_output():
    parsed = Understanding(category="greeting", search_query_en="")
    resp = SimpleNamespace(prompt_feedback=None, parsed=parsed, text="", candidates=[])
    assert await gemini_with(resp).parse("sys", "hi", Understanding) == parsed


async def test_gemini_falls_back_to_json_text():
    text = '{"category": "crop_question", "search_query_en": "rice blast"}'
    resp = SimpleNamespace(prompt_feedback=None, parsed=None, text=text, candidates=[])
    out = await gemini_with(resp).parse("sys", "hi", Understanding)
    assert out.search_query_en == "rice blast"


async def test_gemini_blocked_or_empty_raises():
    blocked = SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason="SAFETY"), parsed=None, text="", candidates=[]
    )
    with pytest.raises(LLMUnavailable):
        await gemini_with(blocked).parse("sys", "hi", Understanding)
    empty = SimpleNamespace(prompt_feedback=None, parsed=None, text=None, candidates=[])
    with pytest.raises(LLMUnavailable):
        await gemini_with(empty).parse("sys", "hi", Understanding)

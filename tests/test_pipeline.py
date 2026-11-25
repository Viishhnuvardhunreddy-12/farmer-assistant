import pytest

from app.config import Settings
from app.llm.client import LLMUnavailable
from app.llm.schemas import Diagnosis, GroundedAnswer, SourceQuote, Understanding
from app.models import IncomingMessage, Media
from app.pipeline import Pipeline
from app.rag.ingest import Chunk
from app.rag.retriever import Retriever
from app.speech.base import NullSpeech
from app.store import Store
from tests.fakes import FakeLLM, HashEmbedding

SOURCE = (
    "Rice blast: diamond shaped spots with grey centre on leaves. "
    "Spray Tricyclazole 75 WP @ 0.6 g/litre of water. Wear gloves and mask while spraying."
)

GOOD_ANSWER = GroundedAnswer(
    answer="This looks like blast. Spray Tricyclazole 0.6 g per litre of water.",
    supported_by_sources=True,
    cited_source_ids=["S1"],
    quotes=[
        SourceQuote(
            source_id="S1", quote="Tricyclazole 75 WP @ 0.6 g/litre of water", kind="dosage"
        ),
        SourceQuote(source_id="S1", quote="Wear gloves and mask while spraying.", kind="safety"),
    ],
    mentions_chemicals=True,
    confidence="high",
)

CROP_Q = Understanding(
    category="crop_question",
    search_query_en="diamond spots grey centre leaves",
    likely_conditions=["rice blast"],
)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, crop="paddy", language_code="en", min_source_similarity=0.1)


@pytest.fixture
def retriever():
    r = Retriever(None, "pipeline_test", embedding_function=HashEmbedding())
    r.rebuild([Chunk("guide-p3-c0", SOURCE, "Paddy Guide", 3)])
    return r


def make(settings, retriever, outputs) -> Pipeline:
    return Pipeline(settings, FakeLLM(outputs), retriever, Store(":memory:", "salt"), NullSpeech())


def text_msg(text: str, msg_id: str = "1") -> IncomingMessage:
    return IncomingMessage(channel="telegram", message_id=msg_id, user_id="42", text=text)


async def consent(p: Pipeline, answer: str = "1") -> None:
    await p.handle(text_msg("hi", "0"))
    await p.handle(text_msg(answer, "c"))


async def test_first_message_asks_consent_and_answers(settings, retriever):
    p = make(settings, retriever, {Understanding: CROP_Q, GroundedAnswer: GOOD_ANSWER})
    replies = await p.handle(text_msg("brown spots on leaves"))
    assert "Reply 1 for YES" in replies[0].text
    assert "Tricyclazole" in replies[1].text


async def test_greeting_only_gets_welcome(settings, retriever):
    greeting = Understanding(category="greeting", search_query_en="", likely_conditions=[])
    p = make(settings, retriever, {Understanding: greeting})
    replies = await p.handle(text_msg("hello"))
    assert len(replies) == 1 and "Reply 1 for YES" in replies[0].text


async def test_telegram_start_command_gets_only_welcome_without_llm(settings, retriever):
    p = make(settings, retriever, {})  # no LLM outputs: any LLM call would fail the test
    replies = await p.handle(text_msg("/start"))
    assert len(replies) == 1 and "Reply 1 for YES" in replies[0].text
    [later] = await p.handle(text_msg("/help", "2"))
    assert "Ask me anything about growing" in later.text
    assert p.llm.calls == []


async def test_consent_reply_is_stored(settings, retriever):
    p = make(
        settings,
        retriever,
        {
            Understanding: Understanding(
                category="greeting", search_query_en="", likely_conditions=[]
            )
        },
    )
    await consent(p, "1")
    assert p.store.get_consent(p.store.user_hash("telegram", "42")) == "yes"


async def test_grounded_answer_shows_verbatim_quotes_and_source(settings, retriever):
    p = make(settings, retriever, {Understanding: CROP_Q, GroundedAnswer: GOOD_ANSWER})
    await consent(p)
    [reply] = await p.handle(text_msg("brown spots on leaves"))
    assert '"Tricyclazole 75 WP @ 0.6 g/litre of water" (Paddy Guide, p. 3)' in reply.text
    assert "Sources: Paddy Guide, p. 3" in reply.text
    log = p.store.interactions()[-1]
    assert log["confidence"] == "high" and log["fallback_reason"] == ""
    assert log["question"] == "brown spots on leaves"  # consented, so content is kept


async def test_invented_dose_is_replaced_by_expert_fallback(settings, retriever):
    bad = GOOD_ANSWER.model_copy(update={"answer": "Spray Tricyclazole 5 g per litre."})
    p = make(settings, retriever, {Understanding: CROP_Q, GroundedAnswer: bad})
    await consent(p)
    [reply] = await p.handle(text_msg("brown spots"))
    assert "contact an expert" in reply.text and "5 g" not in reply.text
    assert p.store.interactions()[-1]["fallback_reason"] == "unverified_number"


async def test_no_matching_sources_falls_back_without_calling_answer_model(settings, retriever):
    settings.min_source_similarity = 0.99
    p = make(settings, retriever, {Understanding: CROP_Q})
    await consent(p)
    [reply] = await p.handle(text_msg("brown spots"))
    assert "contact an expert" in reply.text
    assert GroundedAnswer not in [c[0] for c in p.llm.calls]


async def test_llm_refusal_falls_back(settings, retriever):
    p = make(settings, retriever, {Understanding: LLMUnavailable("refusal")})
    await consent(p)
    [reply] = await p.handle(text_msg("brown spots"))
    assert "contact an expert" in reply.text


async def test_other_crop_question(settings, retriever):
    p = make(
        settings,
        retriever,
        {
            Understanding: Understanding(
                category="other_crop", search_query_en="", likely_conditions=[]
            )
        },
    )
    await consent(p)
    [reply] = await p.handle(text_msg("cotton bollworm?"))
    assert "only have verified information for paddy" in reply.text


async def test_photo_diagnosis_then_grounded_treatment(settings, retriever):
    diag = Diagnosis(
        is_plant_photo=True,
        crop_seen="paddy",
        matches_target_crop=True,
        likely_condition="rice blast",
        alternatives=[],
        visible_symptoms=["diamond spots"],
        confidence="high",
    )
    p = make(settings, retriever, {Diagnosis: diag, GroundedAnswer: GOOD_ANSWER})
    await consent(p)
    msg = text_msg("", "2")
    msg.image = Media(b"\xff\xd8fakejpeg", "image/jpeg")
    [reply] = await p.handle(msg)
    assert reply.text.startswith("Likely problem: rice blast")
    assert "Tricyclazole" in reply.text


async def test_low_confidence_photo_asks_for_better_photo(settings, retriever):
    diag = Diagnosis(
        is_plant_photo=True,
        crop_seen="paddy",
        matches_target_crop=True,
        likely_condition="rice blast",
        alternatives=["brown spot"],
        visible_symptoms=[],
        confidence="low",
    )
    p = make(settings, retriever, {Diagnosis: diag})
    await consent(p)
    msg = text_msg("", "2")
    msg.image = Media(b"x", "image/jpeg")
    [reply] = await p.handle(msg)
    assert "clear, close photo" in reply.text


async def test_voice_without_provider_asks_to_type(settings, retriever):
    p = make(settings, retriever, {})
    await consent(p)
    msg = text_msg("", "3")
    msg.audio = Media(b"ogg", "audio/ogg")
    [reply] = await p.handle(msg)
    assert "type your question" in reply.text


async def test_no_consent_means_no_content_logged(settings, retriever):
    p = make(settings, retriever, {Understanding: CROP_Q, GroundedAnswer: GOOD_ANSWER})
    await consent(p, "2")
    await p.handle(text_msg("brown spots on leaves"))
    log = p.store.interactions()[-1]
    assert log["question"] == "" and log["answer"] == "" and log["consented"] == 0
    assert log["confidence"] == "high"  # metadata is still kept

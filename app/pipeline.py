"""Handles one farmer message end to end. Business logic lives here, not in main.py."""

import logging

from app.config import Settings
from app.llm.client import LLM, LLMUnavailable
from app.llm.prompts import ANSWER_SYSTEM, UNDERSTAND_SYSTEM, answer_user_content, fmt
from app.llm.schemas import GroundedAnswer, Understanding
from app.models import IncomingMessage, InteractionRecord, Reply, RetrievedChunk
from app.rag.retriever import Retriever
from app.safety.guard import GuardResult, check_answer, check_diagnosis
from app.speech.base import SpeechProvider
from app.store import Store
from app.ui_text import t
from app.vision.detector import diagnose, diagnosis_summary

log = logging.getLogger(__name__)

CONSENT_YES = {"1", "yes", "y"}
CONSENT_NO = {"2", "no", "n"}


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        llm: LLM,
        retriever: Retriever,
        store: Store,
        speech: SpeechProvider,
    ):
        self.s = settings
        self.llm = llm
        self.retriever = retriever
        self.store = store
        self.speech = speech

    def _t(self, key: str, **kwargs: str) -> str:
        return t(
            key,
            self.s.language_code,
            crop=self.s.crop,
            expert_contact=self.s.expert_contact,
            **kwargs,
        )

    async def handle(self, msg: IncomingMessage) -> list[Reply]:
        user_hash = self.store.user_hash(msg.channel, msg.user_id)
        consent = self.store.get_consent(user_hash)
        text = msg.text.strip()
        replies: list[Reply] = []

        if consent == "unknown":
            self.store.set_consent(user_hash, "pending")
            replies.append(Reply(self._t("welcome_consent")))
        elif consent == "pending" and not (msg.image or msg.audio):
            if text.lower() in CONSENT_YES:
                self.store.set_consent(user_hash, "yes")
                return [Reply(self._t("consent_yes"))]
            if text.lower() in CONSENT_NO:
                self.store.set_consent(user_hash, "no")
                return [Reply(self._t("consent_no"))]

        record = InteractionRecord(
            channel=msg.channel,
            user_hash=user_hash,
            kind="photo" if msg.image else "voice" if msg.audio else "text",
            question=text,
            model=self.llm.model,
        )
        try:
            reply = await self._answer(msg, record)
        except LLMUnavailable as e:
            log.warning("LLM unavailable: %s", e)
            record.fallback_reason = f"llm_unavailable: {e}"
            reply = Reply(self._t("expert_fallback"))
        except Exception:
            log.exception("Failed to handle message")
            record.fallback_reason = "error"
            reply = Reply(self._t("error"))
        record.answer = reply.text
        self.store.log_interaction(record)

        # Answer a voice note with voice too, when a speech provider is configured.
        if msg.audio and reply.audio is None:
            reply.audio = await self.speech.synthesize(reply.text, self.s.language_code)
        if consent == "unknown" and record.kind == "text" and record.fallback_reason == "greeting":
            return replies  # the welcome message already covers a plain "hello"
        replies.append(reply)
        return replies

    async def _answer(self, msg: IncomingMessage, record: InteractionRecord) -> Reply:
        question = msg.text.strip()
        if msg.audio:
            transcript = await self.speech.transcribe(msg.audio, self.s.language_code)
            if transcript is None:
                record.fallback_reason = "voice_not_supported"
                return Reply(self._t("voice_not_supported"))
            question = f"{transcript}\n{question}".strip()
            record.question = question
        if msg.image:
            return await self._answer_photo(msg, question, record)
        if not question:
            record.fallback_reason = "unsupported_message"
            return Reply(self._t("unsupported_message"))
        return await self._answer_text(question, record)

    async def _answer_text(self, question: str, record: InteractionRecord) -> Reply:
        understanding = await self.llm.parse(
            fmt(UNDERSTAND_SYSTEM, self.s), question, Understanding, effort="low", max_tokens=2000
        )
        if understanding.category != "crop_question":
            record.fallback_reason = understanding.category
            key = {"greeting": "greeting", "other_crop": "other_crop"}.get(
                understanding.category, "out_of_scope"
            )
            return Reply(self._t(key))
        return await self._grounded(question, understanding.search_query_en, record)

    async def _answer_photo(
        self, msg: IncomingMessage, caption: str, record: InteractionRecord
    ) -> Reply:
        assert msg.image is not None
        diagnosis = await diagnose(self.llm, self.s, msg.image, caption)
        record.diagnosis = diagnosis.model_dump()
        reason = check_diagnosis(diagnosis)
        if reason:
            record.fallback_reason = reason
            return Reply(self._t(reason))

        query = f"{self.s.crop} {diagnosis.likely_condition} symptoms management control"
        reply = await self._grounded(caption, query, record, diagnosis_summary(diagnosis))
        if record.fallback_reason:
            return reply
        intro = self._t("diagnosis_intro", condition=diagnosis.likely_condition)
        return Reply(f"{intro}\n\n{reply.text}")

    async def _grounded(
        self, question: str, query: str, record: InteractionRecord, diagnosis_text: str = ""
    ) -> Reply:
        record.search_query = query
        chunks = self.retriever.search(query, self.s.retrieval_top_k, self.s.min_source_similarity)
        record.retrieved_ids = [c.doc_id for c in chunks]
        if not chunks:
            record.fallback_reason = "no_sources"
            return Reply(self._t("expert_fallback"))

        answer = await self.llm.parse(
            fmt(ANSWER_SYSTEM, self.s),
            answer_user_content(question, chunks, diagnosis_text),
            GroundedAnswer,
            effort="medium",
        )
        record.confidence = answer.confidence
        guard = check_answer(answer, chunks)
        if not guard.ok:
            record.fallback_reason = guard.reason
            return Reply(self._t("expert_fallback"))
        return Reply(self._render(answer, guard, chunks))

    def _render(
        self, answer: GroundedAnswer, guard: GuardResult, chunks: list[RetrievedChunk]
    ) -> str:
        by_id = {c.id: c for c in chunks}
        parts = [answer.answer.strip()]
        if guard.quotes:
            lines = [self._t("from_sources")]
            lines += [f'"{q.quote.strip()}" ({by_id[q.source_id].citation})' for q in guard.quotes]
            parts.append("\n".join(lines))
        if guard.add_chemical_safety:
            parts.append(self._t("chemical_safety"))
        if guard.add_expert_note:
            parts.append(self._t("medium_confidence_note"))
        citations = dict.fromkeys(by_id[i].citation for i in answer.cited_source_ids if i in by_id)
        parts.append(self._t("sources") + " " + "; ".join(citations))
        return "\n\n".join(parts)

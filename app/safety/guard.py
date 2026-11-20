"""Deterministic checks between the LLM answer and the farmer. Fail closed.

See CLAUDE.md section 3. Anything we cannot verify against the retrieved source
text is replaced by the expert fallback rather than sent to the farmer.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from app.llm.schemas import Diagnosis, GroundedAnswer, SourceQuote
from app.models import RetrievedChunk

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""
    quotes: list[SourceQuote] = field(default_factory=list)
    add_expert_note: bool = False
    add_chemical_safety: bool = False


def _normalize(text: str) -> str:
    """Unify digits from any script, unicode forms, whitespace and case for comparison."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def numbers_in(text: str) -> set[str]:
    """Numbers in a text, with thousands separators removed (1,000 → 1000; 2.5 stays 2.5)."""
    out = set()
    for match in _NUMBER.findall(_normalize(text)):
        if re.fullmatch(r"\d{1,3}(,\d{3})+", match):
            match = match.replace(",", "")
        out.add(match.replace(",", "."))
    return out


def quote_is_verbatim(quote: str, chunk_text: str) -> bool:
    q = _normalize(quote)
    return bool(q) and q in _normalize(chunk_text)


def check_answer(answer: GroundedAnswer, chunks: list[RetrievedChunk]) -> GuardResult:
    if not chunks:
        return GuardResult(ok=False, reason="no_sources")
    if not answer.supported_by_sources:
        return GuardResult(ok=False, reason="not_supported_by_sources")
    if answer.confidence == "low":
        return GuardResult(ok=False, reason="low_confidence")

    by_id = {c.id: c for c in chunks}
    cited = [by_id[i] for i in answer.cited_source_ids if i in by_id]
    if not cited:
        return GuardResult(ok=False, reason="no_valid_citations")

    valid_quotes: list[SourceQuote] = []
    for q in answer.quotes:
        chunk = by_id.get(q.source_id)
        if chunk and quote_is_verbatim(q.quote, chunk.text):
            valid_quotes.append(q)
        elif q.kind in ("dosage", "safety"):
            return GuardResult(ok=False, reason="unverified_quote")

    supporting_ids = {c.id for c in cited} | {q.source_id for q in valid_quotes}
    source_numbers: set[str] = set()
    for chunk_id in supporting_ids:
        source_numbers |= numbers_in(by_id[chunk_id].text)
    if numbers_in(answer.answer) - source_numbers:
        return GuardResult(ok=False, reason="unverified_number")

    has_safety_quote = any(q.kind == "safety" for q in valid_quotes)
    return GuardResult(
        ok=True,
        quotes=valid_quotes,
        add_expert_note=answer.confidence == "medium",
        add_chemical_safety=answer.mentions_chemicals and not has_safety_quote,
    )


def check_diagnosis(diagnosis: Diagnosis) -> str:
    """Return a fallback reason, or "" if the diagnosis is usable for retrieval."""
    if not diagnosis.is_plant_photo:
        return "not_plant_photo"
    if not diagnosis.matches_target_crop:
        return "other_crop"
    condition = diagnosis.likely_condition.strip().lower()
    # A farmer sending a photo suspects a problem; "healthy" is treated as unclear, not as advice.
    if diagnosis.confidence == "low" or condition in ("", "unknown", "healthy"):
        return "unclear_photo"
    return ""

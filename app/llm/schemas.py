"""Structured outputs for every LLM step. The model must fill these exactly."""

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class Understanding(BaseModel):
    category: Literal["crop_question", "other_crop", "greeting", "off_topic"] = Field(
        description="crop_question = about growing the target crop; other_crop = farming "
        "question about a different crop; greeting = hello/thanks; off_topic = anything else"
    )
    search_query_en: str = Field(
        description="Short English search query for the source documents. Empty unless "
        "category is crop_question."
    )
    likely_conditions: list[str] = Field(
        description="If the farmer describes symptoms, up to 2 English names of the most likely "
        "diseases, pests or deficiencies. Used only to search the documents. Empty otherwise."
    )


class Diagnosis(BaseModel):
    is_plant_photo: bool
    crop_seen: str = Field(description="Crop visible in the photo, in English, or 'unknown'")
    matches_target_crop: bool
    likely_condition: str = Field(
        description="English common name of the most likely disease, pest or deficiency, "
        "'healthy', or 'unknown'"
    )
    alternatives: list[str] = Field(description="Other plausible conditions, most likely first")
    visible_symptoms: list[str] = Field(description="Symptoms actually visible, in English")
    confidence: Confidence


class SourceQuote(BaseModel):
    source_id: str = Field(description="Id of the source chunk, e.g. S2")
    quote: str = Field(description="Exact words copied from that source chunk, unchanged")
    kind: Literal["dosage", "safety", "other"]


class GroundedAnswer(BaseModel):
    answer: str = Field(description="Answer for the farmer in their language, simple words")
    supported_by_sources: bool = Field(
        description="True only if the sources directly support every piece of advice given"
    )
    cited_source_ids: list[str]
    quotes: list[SourceQuote] = Field(
        description="Verbatim quotes for every dosage, rate, timing and safety instruction"
    )
    mentions_chemicals: bool = Field(
        description="True if the answer mentions any pesticide, fungicide, herbicide or fertilizer"
    )
    confidence: Confidence

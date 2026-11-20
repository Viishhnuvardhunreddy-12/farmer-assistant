from dataclasses import dataclass, field
from typing import Literal

Channel = Literal["telegram", "whatsapp", "cli"]


@dataclass
class Media:
    data: bytes
    mime_type: str


@dataclass
class IncomingMessage:
    channel: Channel
    message_id: str
    user_id: str  # chat id / phone number; never stored raw
    text: str = ""  # message text or photo caption
    image: Media | None = None
    audio: Media | None = None


@dataclass
class Reply:
    text: str
    audio: Media | None = None


@dataclass
class RetrievedChunk:
    id: str
    text: str
    source_title: str
    page: int | None
    similarity: float
    doc_id: str = ""  # stable id in the vector store; `id` is the short label shown to the LLM
    section: str = ""

    @property
    def citation(self) -> str:
        return f"{self.source_title}, p. {self.page}" if self.page else self.source_title


@dataclass
class InteractionRecord:
    """What we log for one message. Content fields are dropped without consent."""

    channel: str
    user_hash: str
    kind: str
    question: str = ""
    search_query: str = ""
    diagnosis: dict | None = None
    retrieved_ids: list[str] = field(default_factory=list)
    answer: str = ""
    confidence: str = ""
    fallback_reason: str = ""
    model: str = ""

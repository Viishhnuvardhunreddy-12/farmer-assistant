"""Load trusted source documents, chunk them, and index them in Chroma.

Only files listed in data/sources/sources.json are indexed. That manifest is the
record of which documents were vetted as trustworthy; adding a file to the folder
alone is not enough.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

log = logging.getLogger(__name__)

MANIFEST = "sources.json"
SUPPORTED = {".pdf", ".txt", ".md"}


@dataclass
class Chunk:
    doc_id: str
    text: str
    source_title: str
    page: int | None


def load_manifest(sources_dir: Path) -> dict[str, dict]:
    path = sources_dir / MANIFEST
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_pages(path: Path) -> list[tuple[int | None, str]]:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    return [(None, path.read_text(encoding="utf-8"))]


def chunk_text(text: str, max_chars: int = 1200, overlap_paragraphs: int = 1) -> list[str]:
    """Split on blank lines and pack paragraphs into chunks of up to max_chars."""
    text = re.sub(r"[ \t]+", " ", text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    for para in paragraphs:
        # Very long paragraphs (common in PDF extraction) are split on sentences.
        pieces = [para] if len(para) <= max_chars else _split_long(para, max_chars)
        for piece in pieces:
            if current and len("\n\n".join(current + [piece])) > max_chars:
                chunks.append("\n\n".join(current))
                current = current[-overlap_paragraphs:] if overlap_paragraphs else []
                if len("\n\n".join(current + [piece])) > max_chars:
                    current = []
            current.append(piece)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    buf = ""
    for s in sentences:
        if buf and len(buf) + len(s) + 1 > max_chars:
            out.append(buf)
            buf = ""
        buf = f"{buf} {s}".strip()
        while len(buf) > max_chars:
            out.append(buf[:max_chars])
            buf = buf[max_chars:]
    if buf:
        out.append(buf)
    return out


def build_chunks(sources_dir: Path) -> list[Chunk]:
    manifest = load_manifest(sources_dir)
    chunks: list[Chunk] = []
    for path in sorted(sources_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED or path.name == MANIFEST:
            continue
        meta = manifest.get(path.name)
        if not meta:
            log.warning("Skipping %s: not listed in %s (unvetted source)", path.name, MANIFEST)
            continue
        title = meta.get("title", path.stem)
        for page, text in read_pages(path):
            for i, piece in enumerate(chunk_text(text)):
                page_tag = f"p{page}" if page else "p0"
                chunks.append(Chunk(f"{path.stem}-{page_tag}-c{i}", piece, title, page))
    return chunks

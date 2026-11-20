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
# Keep chunks short: the embedding model only reads roughly the first 1000 characters.
# Whole sections are brought back at search time instead (see Retriever.search_many).
CHUNK_MAX_CHARS = 1200


@dataclass
class Chunk:
    doc_id: str
    text: str
    source_title: str
    page: int | None
    section: str = ""  # chunks of the same heading/page share this, for section expansion


def load_manifest(sources_dir: Path) -> dict[str, dict]:
    path = sources_dir / MANIFEST
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_sections(path: Path) -> list[tuple[int | None, str, str]]:
    """Return (page, heading, text) sections.

    PDFs are split by page. TXT/MD files are split at "## " heading lines; the heading is
    repeated at the top of every chunk of its section, so a chunk that only says
    "Management: ..." can still be found by the disease name in its heading.
    """
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return [(i + 1, "", page.extract_text() or "") for i, page in enumerate(reader.pages)]
    sections: list[tuple[int | None, str, str]] = []
    heading, lines = "", []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            sections.append((None, heading, "\n".join(lines)))
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    sections.append((None, heading, "\n".join(lines)))
    return [s for s in sections if s[2].strip()]


def chunk_text(
    text: str, max_chars: int = CHUNK_MAX_CHARS, overlap_paragraphs: int = 1
) -> list[str]:
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


def build_chunks(sources_dir: Path, crop: str = "") -> list[Chunk]:
    """Chunk every vetted source. With `crop`, documents tagged for another crop are skipped."""
    manifest = load_manifest(sources_dir)
    chunks: list[Chunk] = []
    for path in sorted(sources_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED or path.name == MANIFEST:
            continue
        meta = manifest.get(path.name)
        if not meta:
            log.warning("Skipping %s: not listed in %s (unvetted source)", path.name, MANIFEST)
            continue
        doc_crop = meta.get("crop", "")
        if crop and doc_crop and doc_crop.lower() != crop.lower():
            log.info("Skipping %s: for crop %r, not %r", path.name, doc_crop, crop)
            continue
        title = meta.get("title", path.stem)
        # PDF pages with no advice (cover, foreword, contents, blank forms) only add noise.
        skip_pages = set(meta.get("skip_pages", []))
        n = 0
        for s, (page, heading, text) in enumerate(read_sections(path)):
            if page in skip_pages:
                continue
            page_tag = f"p{page}" if page else "p0"
            # Leave room for the heading so chunks stay within the size limit.
            for piece in chunk_text(text, max_chars=CHUNK_MAX_CHARS - len(heading)):
                text_with_heading = f"{heading}\n{piece}" if heading else piece
                chunk_id = f"{path.stem}-{page_tag}-c{n}"
                chunks.append(Chunk(chunk_id, text_with_heading, title, page, f"{path.stem}-s{s}"))
                n += 1
    return chunks

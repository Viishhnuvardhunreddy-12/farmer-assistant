"""Index the vetted documents in data/sources/ into Chroma."""

import logging

import _bootstrap  # noqa: F401

from app.config import get_settings
from app.rag.ingest import build_chunks, load_manifest
from app.rag.retriever import Retriever

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    s = get_settings()
    if not load_manifest(s.sources_dir):
        raise SystemExit(
            f"No {s.sources_dir}/sources.json found. List your vetted documents there first "
            "(see data/sources/README.md)."
        )
    chunks = build_chunks(s.sources_dir)
    if not chunks:
        raise SystemExit("No text extracted from the listed sources.")
    retriever = Retriever(str(s.chroma_dir), s.collection_name)
    retriever.rebuild(chunks)
    print(f"Indexed {len(chunks)} chunks into '{s.collection_name}'.")


if __name__ == "__main__":
    main()

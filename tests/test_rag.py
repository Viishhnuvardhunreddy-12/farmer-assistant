import json

from app.rag.ingest import build_chunks, chunk_text
from app.rag.retriever import Retriever
from tests.fakes import HashEmbedding


def test_chunk_text_respects_limit():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 40 for i in range(20))
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_text_splits_long_paragraph():
    chunks = chunk_text("Sentence one. " * 200, max_chars=300)
    assert all(len(c) <= 300 for c in chunks)


def test_only_manifest_files_are_indexed(tmp_path):
    (tmp_path / "vetted.txt").write_text("Blast disease control in paddy.")
    (tmp_path / "random_blog.txt").write_text("Spray anything you like.")
    (tmp_path / "sources.json").write_text(json.dumps({"vetted.txt": {"title": "Vetted Guide"}}))
    chunks = build_chunks(tmp_path)
    assert [c.source_title for c in chunks] == ["Vetted Guide"]


def test_retriever_finds_relevant_chunk_and_applies_threshold(tmp_path):
    (tmp_path / "guide.txt").write_text(
        "Rice blast causes diamond shaped spots on leaves.\n\n"
        "Stem borer causes dead heart in young plants."
    )
    (tmp_path / "sources.json").write_text(json.dumps({"guide.txt": {"title": "Guide"}}))
    chunks = build_chunks(tmp_path)

    r = Retriever(None, "test_collection", embedding_function=HashEmbedding())
    r.rebuild(chunks)
    assert r.count() == len(chunks)

    hits = r.search("rice blast diamond spots leaves", top_k=3, min_similarity=0.0)
    assert hits and "blast" in hits[0].text
    assert hits[0].id == "S1"
    assert r.search("completely unrelated tractor loan", top_k=3, min_similarity=0.99) == []

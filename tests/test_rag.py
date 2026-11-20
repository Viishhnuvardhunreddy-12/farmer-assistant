import json

from app.rag.ingest import CHUNK_MAX_CHARS, Chunk, build_chunks, chunk_text
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


def test_headings_are_repeated_in_every_chunk_of_their_section(tmp_path):
    body = "\n\n".join(["Spray as advised. " * 20] * 4)
    (tmp_path / "guide.md").write_text(
        f"## Rice blast: management\n{body}\n## Brown spot: symptoms\nOval brown spots."
    )
    (tmp_path / "sources.json").write_text(json.dumps({"guide.md": {"title": "Guide"}}))
    chunks = build_chunks(tmp_path)
    blast = [c for c in chunks if "Spray" in c.text]
    assert len(blast) > 1
    assert all(c.text.startswith("Rice blast: management\n") for c in blast)
    assert chunks[-1].text == "Brown spot: symptoms\nOval brown spots."
    assert all(len(c.text) <= CHUNK_MAX_CHARS for c in chunks)
    assert len({c.doc_id for c in chunks}) == len(chunks)


def test_search_many_merges_and_relabels():
    r = Retriever(None, "many_test", embedding_function=HashEmbedding())
    r.rebuild(
        [
            Chunk("a", "Rice blast symptoms: spindle shaped spots with grey centre.", "G", None),
            Chunk("b", "Rice blast management: spray as per label.", "G", None),
            Chunk("c", "Stem borer causes dead heart.", "G", None),
        ]
    )
    hits = r.search_many(
        ["spindle shaped spots grey centre", "rice blast management"], top_k=1, min_similarity=0.0
    )
    assert {h.doc_id for h in hits} == {"a", "b"}
    assert [h.id for h in hits] == ["S1", "S2"]


def test_search_many_returns_whole_matching_section(tmp_path):
    filler = "\n\n".join(["Pathogen details and spread. " * 15] * 3)
    (tmp_path / "guide.md").write_text(
        f"## Rice disease: Brown spot (cause and management)\n{filler}\n\n"
        "Management:\nSpray Mancozeb 500 g when grade reaches 3.\n"
        "## Rice disease: Stem borer\nDead heart in young plants."
    )
    (tmp_path / "sources.json").write_text(json.dumps({"guide.md": {"title": "Guide"}}))
    r = Retriever(None, "section_test", embedding_function=HashEmbedding())
    r.rebuild(build_chunks(tmp_path))

    hits = r.search_many(["brown spot pathogen details"], top_k=1, min_similarity=0.0)
    assert len(hits) > 1, "the whole section should come back, not just the best chunk"
    assert any("Mancozeb 500 g" in h.text for h in hits)
    assert not any("Stem borer" in h.text for h in hits)
    assert [h.id for h in hits] == [f"S{i}" for i in range(1, len(hits) + 1)]


def test_only_documents_for_the_chosen_crop_are_indexed(tmp_path):
    for name in ("rice.txt", "chilli.txt", "general.txt"):
        (tmp_path / name).write_text(f"Text from {name}.")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "rice.txt": {"title": "Rice", "crop": "paddy"},
                "chilli.txt": {"title": "Chilli", "crop": "Chilli"},
                "general.txt": {"title": "General"},
            }
        )
    )
    titles = {c.source_title for c in build_chunks(tmp_path, crop="chilli")}
    assert titles == {"Chilli", "General"}
    assert len({c.source_title for c in build_chunks(tmp_path)}) == 3


def test_skip_pages_leaves_out_front_matter(tmp_path, monkeypatch):
    import app.rag.ingest as ingest

    pages = [(1, "", "Foreword by the director."), (2, "", "Spray neem oil 2 ml/L.")]
    monkeypatch.setattr(ingest, "read_sections", lambda path: pages)
    (tmp_path / "booklet.pdf").write_bytes(b"%PDF")
    (tmp_path / "sources.json").write_text(
        json.dumps({"booklet.pdf": {"title": "Booklet", "skip_pages": [1]}})
    )
    assert [c.text for c in build_chunks(tmp_path)] == ["Spray neem oil 2 ml/L."]

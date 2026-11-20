import chromadb

from app.models import RetrievedChunk
from app.rag.ingest import Chunk


class Retriever:
    def __init__(self, persist_dir: str | None, collection: str, embedding_function=None):
        self._client = (
            chromadb.PersistentClient(path=persist_dir)
            if persist_dir
            else chromadb.EphemeralClient()
        )
        self._name = collection
        self._ef = embedding_function
        self._collection = self._get_collection()

    def _get_collection(self):
        kwargs = {"name": self._name, "metadata": {"hnsw:space": "cosine"}}
        if self._ef is not None:
            kwargs["embedding_function"] = self._ef
        return self._client.get_or_create_collection(**kwargs)

    def rebuild(self, chunks: list[Chunk], batch_size: int = 100) -> None:
        """Replace the whole index. Sources are few, so a full rebuild keeps things simple."""
        try:
            self._client.delete_collection(self._name)
        except Exception:  # noqa: BLE001 - collection may not exist yet
            pass
        self._collection = self._get_collection()
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            self._collection.add(
                ids=[c.doc_id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[
                    {"source_title": c.source_title, "page": c.page or 0, "section": c.section}
                    for c in batch
                ],
            )

    def count(self) -> int:
        return self._collection.count()

    def search(self, query: str, top_k: int, min_similarity: float) -> list[RetrievedChunk]:
        if not query.strip() or self.count() == 0:
            return []
        res = self._collection.query(query_texts=[query], n_results=min(top_k, self.count()))
        out: list[RetrievedChunk] = []
        for doc_id, text, meta, dist in zip(
            res["ids"][0],
            res["documents"][0],
            res["metadatas"][0],
            res["distances"][0],
            strict=True,
        ):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            out.append(_to_chunk(f"S{len(out) + 1}", doc_id, text, meta, similarity))
        return out

    def _section_chunks(self, section: str, similarity: float) -> list[RetrievedChunk]:
        res = self._collection.get(where={"section": section})
        return [
            _to_chunk("", doc_id, text, meta, similarity)
            for doc_id, text, meta in zip(
                res["ids"], res["documents"], res["metadatas"], strict=True
            )
        ]

    def search_many(
        self,
        queries: list[str],
        top_k: int,
        min_similarity: float,
        max_sections: int = 4,
        max_total: int = 12,
    ) -> list[RetrievedChunk]:
        """Search several queries and return the best-matching sections in full.

        A section's management advice is often in a different chunk from the symptoms that
        matched the query, so every chunk of the top sections is included, in document order.
        Ids are relabelled S1..Sn.
        """
        best: dict[str, RetrievedChunk] = {}
        for query in queries:
            for chunk in self.search(query, top_k, min_similarity):
                kept = best.get(chunk.doc_id)
                if kept is None or chunk.similarity > kept.similarity:
                    best[chunk.doc_id] = chunk
        ranked = sorted(best.values(), key=lambda c: c.similarity, reverse=True)

        out: list[RetrievedChunk] = []
        seen: set[str] = set()
        sections: list[str] = []
        for hit in ranked:
            if len(out) >= max_total:
                break
            if hit.section and hit.section not in sections and len(sections) < max_sections:
                sections.append(hit.section)
                group = sorted(self._section_chunks(hit.section, hit.similarity), key=_chunk_order)
            elif hit.section in sections:
                continue  # already added with its section
            else:
                group = [hit]
            for chunk in group:
                if chunk.doc_id not in seen and len(out) < max_total:
                    seen.add(chunk.doc_id)
                    out.append(chunk)
        for i, chunk in enumerate(out, start=1):
            chunk.id = f"S{i}"
        return out


def _chunk_order(chunk: RetrievedChunk) -> int:
    return int(chunk.doc_id.rsplit("-c", 1)[-1])


def _to_chunk(label: str, doc_id: str, text: str, meta: dict, similarity: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=label,
        text=text,
        source_title=str(meta.get("source_title", "")),
        page=int(meta.get("page") or 0) or None,
        similarity=similarity,
        doc_id=doc_id,
        section=str(meta.get("section", "")),
    )

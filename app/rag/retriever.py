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
                metadatas=[{"source_title": c.source_title, "page": c.page or 0} for c in batch],
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
            out.append(
                RetrievedChunk(
                    id=f"S{len(out) + 1}",
                    text=text,
                    source_title=str(meta.get("source_title", "")),
                    page=int(meta.get("page") or 0) or None,
                    similarity=similarity,
                    doc_id=doc_id,
                )
            )
        return out

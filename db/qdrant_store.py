"""
db/qdrant_store.py — Qdrant Cloud for book chunk vector search.

Collection: book_chunks
  vector: 768-dim from nomic-embed-text-v1
  payload: text, book, section, verse, characters, topics, citation
"""
from __future__ import annotations
import logging
from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    SearchRequest, ScoredPoint,
)

logger = logging.getLogger(__name__)

# all-MiniLM-L6-v2 produces 384-dim vectors (fast, free, runs on M2)
EMBED_DIM = 384


class QdrantStore:
    """
    Qdrant vector store for book chunks.
    Handles collection creation, upsert, and search.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        collection_name: str = "book_chunks",
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url, api_key=api_key)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        from qdrant_client.models import PayloadSchemaType
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=EMBED_DIM,
                    distance=Distance.COSINE,
                ),
            )
            # Create payload indexes required for filtered search
            self.client.create_payload_index(self.collection_name, "book",       PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(self.collection_name, "characters", PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(self.collection_name, "topics",     PayloadSchemaType.KEYWORD)
            logger.info(f"Created Qdrant collection: {self.collection_name}")
        else:
            count = self.client.count(self.collection_name).count
            # Ensure indexes exist on existing collections too
            try:
                self.client.create_payload_index(self.collection_name, "book",       PayloadSchemaType.KEYWORD)
                self.client.create_payload_index(self.collection_name, "characters", PayloadSchemaType.KEYWORD)
                self.client.create_payload_index(self.collection_name, "topics",     PayloadSchemaType.KEYWORD)
            except Exception:
                pass  # indexes already exist
            logger.info(f"Qdrant collection ready: {self.collection_name} ({count:,} chunks)")

    def upsert_chunks(self, chunks: list[dict]) -> int:
        """
        Upsert chunks with embeddings into Qdrant.
        Each chunk must have: id, embedding, text, book, section_name,
                              section_number, verse_start, verse_end,
                              characters, topics, source_citation
        """
        if not chunks:
            return 0

        points = []
        for chunk in chunks:
            d = chunk if isinstance(chunk, dict) else chunk.to_dict()
            point = PointStruct(
                id=self._make_int_id(d["chunk_id"]),
                vector=d["embedding"],
                payload={
                    "chunk_id":       d["chunk_id"],
                    "text":           d.get("text", ""),
                    "clean_text":     d.get("clean_text", d.get("text", "")),
                    "book":           d["book"],
                    "section_name":   d["section_name"],
                    "section_number": d["section_number"],
                    "verse_start":    d.get("verse_start"),
                    "verse_end":      d.get("verse_end"),
                    "characters":     d.get("characters", []),
                    "topics":         d.get("topics", []),
                    "source_citation":d["source_citation"],
                    "inline_ref":     d.get("inline_ref", ""),
                    "token_count":    d.get("token_count", 0),
                },
            )
            points.append(point)

        # Upsert in batches of 100
        batch_size = 100
        inserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i: i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            inserted += len(batch)
            logger.debug(f"Upserted batch {i // batch_size + 1}: {len(batch)} points")

        logger.info(f"Upserted {inserted} chunks into Qdrant")
        return inserted

    def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        book_filter: str | None = None,
        character_filter: str | None = None,
    ) -> list[dict]:
        """
        Vector similarity search with optional filters.
        Returns list of dicts with text, metadata, and score.
        """
        query_filter = self._build_filter(book_filter, character_filter)

        results: list[ScoredPoint] = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "chunk_id":       r.payload["chunk_id"],
                "text":           r.payload.get("text", ""),
                "clean_text":     r.payload.get("clean_text", r.payload.get("text", "")),
                "book":           r.payload["book"],
                "section_name":   r.payload["section_name"],
                "section_number": r.payload["section_number"],
                "verse_start":    r.payload.get("verse_start"),
                "verse_end":      r.payload.get("verse_end"),
                "characters":     r.payload.get("characters", []),
                "topics":         r.payload.get("topics", []),
                "source_citation":r.payload["source_citation"],
                "inline_ref":     r.payload.get("inline_ref", ""),
                "score":          r.score,
            }
            for r in results
        ]

    def get_all_for_bm25(self, book_filter: str | None = None) -> list[dict]:
        """
        Fetch all chunks for building the local BM25 index.
        Called once at startup.
        """
        scroll_filter = None
        if book_filter:
            scroll_filter = Filter(
                must=[FieldCondition(key="book", match=MatchValue(value=book_filter))]
            )

        all_docs = []
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_docs.extend([
                {
                    "chunk_id": r.payload["chunk_id"],
                    "text": r.payload["text"],
                    "book": r.payload["book"],
                    "section_name": r.payload["section_name"],
                    "section_number": r.payload["section_number"],
                    "verse_start": r.payload.get("verse_start"),
                    "verse_end": r.payload.get("verse_end"),
                    "characters": r.payload.get("characters", []),
                    "topics": r.payload.get("topics", []),
                    "source_citation": r.payload["source_citation"],
                }
                for r in results
            ])
            if offset is None:
                break

        return all_docs

    def get_stats(self) -> dict:
        """Return collection statistics."""
        count = self.client.count(self.collection_name).count
        return {"total_chunks": count, "collection": self.collection_name, "embed_dim": EMBED_DIM}

    def get_existing_ids(self) -> set[str]:
        """Return all existing chunk_ids for deduplication during ingestion."""
        existing = set()
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=["chunk_id"],
                with_vectors=False,
            )
            for r in results:
                if r.payload and "chunk_id" in r.payload:
                    existing.add(r.payload["chunk_id"])
            if offset is None:
                break
        return existing

    @staticmethod
    def _make_int_id(chunk_id: str) -> int:
        """Convert hex chunk_id to integer for Qdrant (requires int or UUID ids)."""
        return int(chunk_id[:16], 16)

    @staticmethod
    def _build_filter(
        book: str | None,
        character: str | None,
    ) -> Filter | None:
        conditions = []
        if book:
            conditions.append(
                FieldCondition(key="book", match=MatchValue(value=book))
            )
        if character:
            conditions.append(
                FieldCondition(key="characters", match=MatchValue(value=character))
            )
        if not conditions:
            return None
        return Filter(must=conditions)
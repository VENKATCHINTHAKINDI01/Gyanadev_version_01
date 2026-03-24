"""
rag/retriever.py — Hybrid retrieval: Qdrant vector search + local BM25.

Dense (Qdrant): captures semantic meaning, handles paraphrasing
BM25 (local):   precise for character names like "Arjuna", "Hanuman"
Final score = alpha * dense + (1 - alpha) * bm25
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
from db.qdrant_store import QdrantStore
from groq_client.client import GroqClient

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id:       str
    text:           str
    book:           str
    section_name:   str
    section_number: int
    verse_start:    int | None
    verse_end:      int | None
    characters:     list[str]
    topics:         list[str]
    source_citation:str
    dense_score:    float
    bm25_score:     float
    hybrid_score:   float

    def to_prompt_block(self) -> str:
        return f"[SOURCE: {self.source_citation}]\n{self.text}"


class HybridRetriever:
    def __init__(
        self,
        qdrant: QdrantStore,
        groq: GroqClient,
        alpha: float = 0.6,
        top_k: int = 20,
    ):
        self.qdrant = qdrant
        self.groq   = groq
        self.alpha  = alpha
        self.top_k  = top_k
        self._bm25: BM25Okapi | None = None
        self._bm25_docs: list[dict] | None = None

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        book_filter: str | None = None,
        character_filter: str | None = None,
    ) -> list[RetrievedChunk]:
        k = top_k or self.top_k

        # 1. Embed query
        query_vec = self.groq.embed_query(query)

        # 2. Dense retrieval via Qdrant
        dense = self.qdrant.search(
            query_vector=query_vec,
            top_k=k,
            book_filter=book_filter,
            character_filter=character_filter,
        )

        # 3. BM25 keyword retrieval
        bm25 = self._bm25_search(query, book_filter, k)

        # 4. Merge and score
        merged = self._merge(dense, bm25)
        merged.sort(key=lambda x: x.hybrid_score, reverse=True)
        return merged[:k]

    def build_bm25_index(self) -> None:
        """Build BM25 index from all Qdrant docs. Call once after ingestion."""
        logger.info("Building BM25 index from Qdrant...")
        docs = self.qdrant.get_all_for_bm25()
        if not docs:
            logger.warning("No documents in Qdrant for BM25 index")
            self._bm25_docs = []
            self._bm25 = BM25Okapi([[]])
            return
        self._bm25_docs = docs
        tokenized = [d["text"].lower().split() for d in docs]
        self._bm25 = BM25Okapi(tokenized)
        logger.info(f"BM25 index built: {len(docs):,} documents")

    def _bm25_search(
        self, query: str, book_filter: str | None, top_k: int
    ) -> list[dict]:
        if self._bm25 is None:
            self.build_bm25_index()
        if not self._bm25_docs:
            return []

        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)

        results = []
        for i, score in enumerate(scores):
            if score <= 0:
                continue
            doc = self._bm25_docs[i]
            if book_filter and doc.get("book") != book_filter:
                continue
            results.append({**doc, "score": float(score)})

        if results:
            max_s = max(r["score"] for r in results)
            if max_s > 0:
                for r in results:
                    r["score"] /= max_s

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _merge(self, dense: list[dict], bm25: list[dict]) -> list[RetrievedChunk]:
        by_id: dict[str, dict] = {}

        for r in dense:
            cid = r["chunk_id"]
            by_id.setdefault(cid, {**r, "dense_score": 0.0, "bm25_score": 0.0})
            by_id[cid]["dense_score"] = r.get("score", 0.0)

        for r in bm25:
            cid = r["chunk_id"]
            by_id.setdefault(cid, {**r, "dense_score": 0.0, "bm25_score": 0.0})
            by_id[cid]["bm25_score"] = max(by_id[cid]["bm25_score"], r.get("score", 0.0))

        chunks = []
        for r in by_id.values():
            hybrid = self.alpha * r["dense_score"] + (1 - self.alpha) * r["bm25_score"]
            chunks.append(RetrievedChunk(
                chunk_id=r["chunk_id"],
                text=r.get("text", ""),
                book=r.get("book", ""),
                section_name=r.get("section_name", ""),
                section_number=int(r.get("section_number", 0)),
                verse_start=r.get("verse_start"),
                verse_end=r.get("verse_end"),
                characters=r.get("characters", []),
                topics=r.get("topics", []),
                source_citation=r.get("source_citation", ""),
                dense_score=r["dense_score"],
                bm25_score=r["bm25_score"],
                hybrid_score=hybrid,
            ))
        return chunks
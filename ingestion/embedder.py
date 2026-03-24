"""
ingestion/embedder.py — Embed chunks via Groq and store in Qdrant.

Credit-efficient:
  - Checks existing Qdrant IDs before embedding (never re-embeds)
  - Batch size 96 (Groq max)
  - Checkpoint file for resuming interrupted ingestion
"""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path

from db.qdrant_store import QdrantStore
from groq_client.client import GroqClient
from ingestion.chunker import Chunk

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    def __init__(
        self,
        groq_client: GroqClient,
        qdrant_store: QdrantStore,
        batch_size: int = 96,
        checkpoint_dir: str = "./data/checkpoints",
    ):
        self.groq = groq_client
        self.qdrant = qdrant_store
        self.batch_size = batch_size
        self.checkpoint_path = Path(checkpoint_dir) / "embedded_ids.json"
        Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

    def upsert_chunks(self, chunks: list[Chunk], show_progress: bool = True) -> int:
        """
        Embed and upsert chunks into Qdrant.
        Skips chunks already embedded (saves Groq tokens).
        Returns number of new chunks inserted.
        """
        # Deduplication: checkpoint file + live Qdrant IDs
        checkpoint_ids = self._load_checkpoint()
        qdrant_ids     = self.qdrant.get_existing_ids()
        existing       = checkpoint_ids | qdrant_ids

        new_chunks = [c for c in chunks if c.chunk_id not in existing]
        if not new_chunks:
            logger.info("All chunks already embedded — skipping")
            return 0

        logger.info(
            f"Embedding {len(new_chunks)} new chunks "
            f"(skipping {len(chunks) - len(new_chunks)} existing)"
        )

        inserted = 0
        for i in range(0, len(new_chunks), self.batch_size):
            batch = new_chunks[i: i + self.batch_size]
            texts = [c.text for c in batch]

            t0 = time.perf_counter()
            try:
                embeddings = self.groq.embed_passages(texts)
            except Exception as e:
                logger.error(f"Groq embedding failed for batch {i}: {e}")
                continue
            elapsed = time.perf_counter() - t0

            # Attach embeddings to chunk dicts
            docs = []
            for chunk, emb in zip(batch, embeddings):
                d = chunk.to_dict()
                d["embedding"] = emb
                docs.append(d)

            self.qdrant.upsert_chunks(docs)

            # Update checkpoint
            for chunk in batch:
                existing.add(chunk.chunk_id)
            self._save_checkpoint(existing)

            inserted += len(batch)
            if show_progress:
                pct = (i + len(batch)) / len(new_chunks) * 100
                logger.info(
                    f"  [{pct:5.1f}%] {len(batch)} chunks embedded in {elapsed:.1f}s"
                )

        logger.info(f"✓ Embedded and stored {inserted} new chunks")
        return inserted

    def _load_checkpoint(self) -> set[str]:
        if self.checkpoint_path.exists():
            with open(self.checkpoint_path) as f:
                return set(json.load(f))
        return set()

    def _save_checkpoint(self, ids: set[str]) -> None:
        with open(self.checkpoint_path, "w") as f:
            json.dump(list(ids), f)
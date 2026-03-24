"""
groq_client/client.py — Groq unified client.

Handles:
  - LLM chat (llama-3.3-70b-versatile) — 500K tokens/day free
  - Embeddings (nomic-embed-text-v1) — for book chunk vectors
  - Streaming responses — low latency for real-time teacher feel
"""
from __future__ import annotations
import logging
from typing import Iterator
from groq import Groq

logger = logging.getLogger(__name__)


class GroqClient:
    def __init__(
        self,
        api_key: str,
        llm_model: str = "llama-3.3-70b-versatile",
        embed_model: str = "nomic-embed-text-v1",
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ):
        self.client = Groq(api_key=api_key)
        self.llm_model = llm_model
        self.embed_model = embed_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"Groq client ready | LLM={llm_model}")

    # ── Embeddings (local via sentence-transformers) ──────────────
    # Groq does not support embedding models.
    # We use all-MiniLM-L6-v2 locally — fast on M2, 384-dim, free forever.

    _embed_model_instance = None  # shared across all GroqClient instances

    def _get_embed_model(self):
        if GroqClient._embed_model_instance is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading local embedding model: all-MiniLM-L6-v2 (first time only ~50MB)")
            GroqClient._embed_model_instance = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded ✓")
        return GroqClient._embed_model_instance

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts using local sentence-transformers."""
        if not texts:
            return []
        model = self._get_embed_model()
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)
        return [e.tolist() for e in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
        model = self._get_embed_model()
        return model.encode([query])[0].tolist()

    def embed_passages(self, passages: list[str]) -> list[list[float]]:
        """Embed document passages (same model as queries for MiniLM)."""
        return self.embed(passages)

    # ── LLM Generation ────────────────────────────────────────────

    def generate(self, system_prompt: str, user_message: str) -> str:
        """
        Generate a response. temperature=0 for grounded teaching.
        """
        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content.strip()

    def generate_with_history(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
    ) -> str:
        """
        Generate using full conversation history.
        history = [{"role": "user"/"assistant", "content": "..."}]
        """
        messages = [{"role": "system", "content": system_prompt}]
        # Include last 10 turns to stay within context window
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content.strip()

    def stream_with_history(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
    ) -> Iterator[str]:
        """
        Streaming response with history — for real-time teacher feel.
        Yields text chunks as they arrive from Groq.
        """
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        stream = self.client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
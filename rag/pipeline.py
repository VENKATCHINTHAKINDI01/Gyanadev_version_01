"""
rag/pipeline.py — End-to-end RAG pipeline for GyanaDev Guru.

Flow:
  Student question
    → language detection
    → translate to English (if needed)
    → scope guard
    → hybrid retrieval (Qdrant + BM25)
    → Guru generates grounded answer with student context
    → faithfulness check
    → translate back to student's language
    → pronunciation correction note appended
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field

from api.config import Settings
from db.mongo_store import AsyncMongoStore
from db.qdrant_store import QdrantStore
from groq_client.client import GroqClient
from guru.teacher import Guru
from memory.pronunciation_tracker import PronunciationCoach
from memory.session_manager import SessionManager
from multilingual.sarvam import LanguageDetector, SarvamTranslator
from rag.guardrails import GuardrailResult, Guardrails, SafetyVerdict
from rag.retriever import HybridRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class GyanadevaResponse:
    answer:           str
    sources:          list[str]
    language:         str
    is_grounded:      bool
    faithfulness:     float
    is_out_of_scope:  bool
    pronunciation_correction: str | None
    latency_ms:       dict[str, float] = field(default_factory=dict)


class GyanadevaRAGPipeline:
    """
    Full pipeline: student question → personalised grounded answer.
    Wires together Guru + Memory + RAG + Voice + Guardrails.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._groq:      GroqClient | None = None
        self._qdrant:    QdrantStore | None = None
        self._mongo:     AsyncMongoStore | None = None
        self._retriever: HybridRetriever | None = None
        self._guru:      Guru | None = None
        self._guardrails:Guardrails | None = None
        self._session_mgr: SessionManager | None = None
        self._coach:     PronunciationCoach | None = None
        self._detector:  LanguageDetector | None = None
        self._translator:SarvamTranslator | None = None

    # ── Lazy-init properties ──────────────────────────────────────

    @property
    def groq(self) -> GroqClient:
        if not self._groq:
            self._groq = GroqClient(
                api_key=self.settings.groq_api_key,
                llm_model=self.settings.groq_llm_model,
                temperature=self.settings.groq_temperature,
                max_tokens=self.settings.groq_max_tokens,
            )
        return self._groq

    @property
    def qdrant(self) -> QdrantStore:
        if not self._qdrant:
            self._qdrant = QdrantStore(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key,
                collection_name=self.settings.qdrant_collection,
            )
        return self._qdrant

    @property
    def mongo(self) -> AsyncMongoStore:
        if not self._mongo:
            self._mongo = AsyncMongoStore(
                uri=self.settings.mongodb_uri,
                db_name=self.settings.mongodb_db,
            )
        return self._mongo

    @property
    def retriever(self) -> HybridRetriever:
        if not self._retriever:
            self._retriever = HybridRetriever(
                qdrant=self.qdrant,
                groq=self.groq,
                alpha=self.settings.hybrid_alpha,
                top_k=self.settings.top_k_retrieval,
            )
        return self._retriever

    @property
    def guru(self) -> Guru:
        if not self._guru:
            self._guru = Guru(groq_client=self.groq)
        return self._guru

    @property
    def guardrails(self) -> Guardrails:
        if not self._guardrails:
            self._guardrails = Guardrails(
                min_faithfulness=self.settings.min_faithfulness_score
            )
        return self._guardrails

    @property
    def session_mgr(self) -> SessionManager:
        if not self._session_mgr:
            self._session_mgr = SessionManager(mongo=self.mongo)
        return self._session_mgr

    @property
    def coach(self) -> PronunciationCoach:
        if not self._coach:
            self._coach = PronunciationCoach(mongo=self.mongo)
        return self._coach

    @property
    def detector(self) -> LanguageDetector:
        if not self._detector:
            self._detector = LanguageDetector()
        return self._detector

    @property
    def translator(self) -> SarvamTranslator:
        if not self._translator:
            self._translator = SarvamTranslator(api_key=self.settings.sarvam_api_key)
        return self._translator

    # ── Main entry point ──────────────────────────────────────────

    async def answer(
        self,
        student_id: str,
        question: str,
        language: str = "auto",
        book_filter: str | None = None,
    ) -> GyanadevaResponse:
        """
        Generate a personalised, grounded answer for a student.

        1. Detect language
        2. Translate question to English
        3. Check scope
        4. Load student context + conversation history
        5. Retrieve relevant book passages (hybrid)
        6. Guru generates answer with student context + history
        7. Faithfulness check
        8. Save turn to memory
        9. Update scores
        10. Return response
        """
        timings: dict[str, float] = {}
        t_total = time.perf_counter()

        # 1. Language detection
        if language == "auto":
            language = self.detector.detect(question)

        # 2. Translate to English for retrieval
        t0 = time.perf_counter()
        english_query = self.translator.to_english(question, language)
        timings["translate_ms"] = (time.perf_counter() - t0) * 1000

        # 3. Scope check
        if not self.guardrails.is_in_scope(english_query):
            return GyanadevaResponse(
                answer=self.guardrails.out_of_scope_message(language),
                sources=[], language=language,
                is_grounded=False, faithfulness=1.0,
                is_out_of_scope=True, pronunciation_correction=None,
            )

        # 4. Load student context
        t0 = time.perf_counter()
        context = await self.session_mgr.get_session_context(student_id)
        student = context.get("student", {})
        history = context.get("history", [])
        teaching_level = context.get("teaching_level", 2)
        timings["context_ms"] = (time.perf_counter() - t0) * 1000

        # 5. Pronunciation check on the original (possibly spoken) question
        t0 = time.perf_counter()
        pronunciation_note = await self.coach.log_and_build_correction(
            student_id=student_id,
            transcript=question,
            student_name=student.get("name", "Student"),
        )
        timings["pronunciation_ms"] = (time.perf_counter() - t0) * 1000

        # 6. Hybrid retrieval
        t0 = time.perf_counter()
        candidates = self.retriever.retrieve(
            query=english_query,
            top_k=self.settings.top_k_retrieval,
            book_filter=book_filter,
        )
        # Rerank: take top-k by hybrid score
        top_chunks = sorted(candidates, key=lambda c: c.hybrid_score, reverse=True)[
            :self.settings.top_k_rerank
        ]
        timings["retrieval_ms"] = (time.perf_counter() - t0) * 1000

        # 7. Build context and system prompt
        context_text = self.guru.format_context(top_chunks)
        system_prompt = self.guru.build_system_prompt(
            student=student,
            context_passages=context_text,
            teaching_level=teaching_level,
            pronunciation_note=pronunciation_note or "",
        )

        # 8. Generate answer using Groq with full conversation history
        t0 = time.perf_counter()
        history_messages = self.session_mgr.history_to_messages(history)
        answer_text = self.guru.generate(
            system_prompt=system_prompt,
            history=history_messages,
            user_question=english_query,
        )
        timings["generation_ms"] = (time.perf_counter() - t0) * 1000

        # 9. Faithfulness check
        guardrail = self.guardrails.check_faithfulness(
            query=english_query,
            answer=answer_text,
            context_chunks=[c.text for c in top_chunks],
        )
        if not guardrail.is_safe and guardrail.safe_fallback:
            answer_text = guardrail.safe_fallback

        # 10. Translate answer back to student's language
        if language != "en":
            t0 = time.perf_counter()
            answer_text = self.translator.from_english(answer_text, language)
            timings["translate_back_ms"] = (time.perf_counter() - t0) * 1000

        # 11. Save turn to memory
        top_book = top_chunks[0].book if top_chunks else None
        top_char = top_chunks[0].characters[0] if top_chunks and top_chunks[0].characters else None
        await self.session_mgr.save_turn(
            student_id=student_id,
            user_message=question,
            assistant_response=answer_text,
            book=top_book,
            topic=english_query[:60],
            character=top_char,
            sources=[c.source_citation for c in top_chunks],
            language=language,
        )

        # 12. Update scores
        quality = self.guru.estimate_response_quality(answer_text)
        await self.session_mgr.update_scores_after_turn(
            student_id=student_id,
            question_length=len(question),
            response_quality=quality if guardrail.is_safe else 0.0,
        )

        timings["total_ms"] = (time.perf_counter() - t_total) * 1000
        logger.info(
            f"Guru answered | {timings['total_ms']:.0f}ms | "
            f"retrieved={len(candidates)} | grounded={guardrail.is_safe}"
        )

        return GyanadevaResponse(
            answer=answer_text,
            sources=[c.source_citation for c in top_chunks],
            language=language,
            is_grounded=guardrail.is_safe,
            faithfulness=guardrail.faithfulness_score,
            is_out_of_scope=False,
            pronunciation_correction=pronunciation_note,
            latency_ms=timings,
        )
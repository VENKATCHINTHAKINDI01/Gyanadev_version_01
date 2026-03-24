"""
api/routes/guru.py — Main Q&A endpoint for the AI Guru.

POST /api/v1/guru/ask        — Ask a question (text response)
POST /api/v1/guru/ask/stream — Streaming response (SSE)
GET  /api/v1/guru/welcome    — Get welcome-back message
"""
from __future__ import annotations
import logging
from typing import AsyncIterator, Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from api.config import Settings, get_settings
from auth.routes import get_current_student
from rag.pipeline import GyanadevaRAGPipeline, GyanadevaResponse
from memory.session_manager import SessionManager
from db.mongo_store import AsyncMongoStore

logger = logging.getLogger(__name__)
router = APIRouter()

_pipeline: GyanadevaRAGPipeline | None = None
_mongo: AsyncMongoStore | None = None


def get_pipeline(settings: Settings = Depends(get_settings)) -> GyanadevaRAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = GyanadevaRAGPipeline(settings)
    return _pipeline


def get_mongo(settings: Settings = Depends(get_settings)) -> AsyncMongoStore:
    global _mongo
    if _mongo is None:
        _mongo = AsyncMongoStore(uri=settings.mongodb_uri, db_name=settings.mongodb_db)
    return _mongo


# ── Request / Response models ──────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    language: str = Field("auto", description="'auto' or ISO code: hi, te, ta, ...")
    book_filter: Literal["mahabharata", "ramayana", "bhagavad_gita"] | None = None

    @field_validator("question")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    language: str
    is_grounded: bool
    faithfulness_score: float
    pronunciation_correction: str | None
    latency_ms: dict[str, float]


# ── Routes ─────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
async def ask_guru(
    request: AskRequest,
    current_student: dict = Depends(get_current_student),
    pipeline: GyanadevaRAGPipeline = Depends(get_pipeline),
) -> AskResponse:
    """
    Ask the Guru a question. Requires authentication.
    The Guru remembers your conversation history and teaches accordingly.
    """
    student_id = current_student["student_id"]
    try:
        resp: GyanadevaResponse = await pipeline.answer(
            student_id=student_id,
            question=request.question,
            language=request.language,
            book_filter=request.book_filter,
        )
    except Exception as e:
        logger.error(f"Pipeline error for {student_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="The Guru encountered an error. Please try again.")

    return AskResponse(
        answer=resp.answer,
        sources=resp.sources,
        language=resp.language,
        is_grounded=resp.is_grounded,
        faithfulness_score=resp.faithfulness,
        pronunciation_correction=resp.pronunciation_correction,
        latency_ms=resp.latency_ms,
    )


@router.post("/ask/stream")
async def ask_guru_stream(
    request: AskRequest,
    current_student: dict = Depends(get_current_student),
    pipeline: GyanadevaRAGPipeline = Depends(get_pipeline),
) -> StreamingResponse:
    """
    Streaming version of /ask. Returns Server-Sent Events.
    Use this in the UI for the real-time typewriter teacher effect.
    """
    student_id = current_student["student_id"]
    language = request.language
    if language == "auto":
        language = pipeline.detector.detect(request.question)

    english_query = pipeline.translator.to_english(request.question, language)

    if not pipeline.guardrails.is_in_scope(english_query):
        async def oos_stream():
            msg = pipeline.guardrails.out_of_scope_message(language)
            yield f"data: {msg}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(oos_stream(), media_type="text/event-stream")

    context = await pipeline.session_mgr.get_session_context(student_id)
    student = context.get("student", {})
    history = context.get("history", [])
    teaching_level = context.get("teaching_level", 2)

    candidates = pipeline.retriever.retrieve(
        query=english_query,
        top_k=pipeline.settings.top_k_retrieval,
        book_filter=request.book_filter,
    )
    top_chunks = sorted(candidates, key=lambda c: c.hybrid_score, reverse=True)[
        :pipeline.settings.top_k_rerank
    ]

    pronunciation_note = await pipeline.coach.log_and_build_correction(
        student_id=student_id,
        transcript=request.question,
        student_name=student.get("name", "Student"),
    )

    context_text = pipeline.guru.format_context(top_chunks)
    system_prompt = pipeline.guru.build_system_prompt(
        student=student,
        context_passages=context_text,
        teaching_level=teaching_level,
        pronunciation_note=pronunciation_note or "",
    )
    history_messages = pipeline.session_mgr.history_to_messages(history)

    async def event_stream() -> AsyncIterator[str]:
        full_answer = ""
        for chunk in pipeline.guru.stream(system_prompt, history_messages, english_query):
            full_answer += chunk
            yield f"data: {chunk}\n\n"

        # Save to memory after streaming completes
        top_book = top_chunks[0].book if top_chunks else None
        top_char = top_chunks[0].characters[0] if top_chunks and top_chunks[0].characters else None
        await pipeline.session_mgr.save_turn(
            student_id=student_id,
            user_message=request.question,
            assistant_response=full_answer,
            book=top_book,
            topic=english_query[:60],
            character=top_char,
            language=language,
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/welcome")
async def get_welcome(
    current_student: dict = Depends(get_current_student),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> dict:
    """
    Get the personalised welcome-back message for a returning student.
    Call this once when student logs in.
    """
    mgr = SessionManager(mongo=mongo)
    message = await mgr.get_welcome_back_message(current_student["student_id"])
    return {
        "message": message,
        "is_returning": message is not None,
        "student_name": current_student.get("name", ""),
        "last_book": current_student.get("last_book"),
        "last_topic": current_student.get("last_topic"),
        "streak": current_student.get("streak", 0),
    }
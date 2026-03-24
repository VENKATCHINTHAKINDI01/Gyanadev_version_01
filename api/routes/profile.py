"""
api/routes/profile.py — Student profile and learning progress.

GET  /api/v1/student/profile          — Full student profile
GET  /api/v1/student/progress         — Learning scores and streak
GET  /api/v1/student/pronunciation    — Pronunciation error history
PATCH /api/v1/student/preferences     — Update language/voice preferences
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.config import Settings, get_settings
from auth.routes import get_current_student
from db.mongo_store import AsyncMongoStore

logger = logging.getLogger(__name__)
router = APIRouter()

_mongo: AsyncMongoStore | None = None


def get_mongo(settings: Settings = Depends(get_settings)) -> AsyncMongoStore:
    global _mongo
    if _mongo is None:
        _mongo = AsyncMongoStore(uri=settings.mongodb_uri, db_name=settings.mongodb_db)
    return _mongo


class PreferencesUpdate(BaseModel):
    preferred_language: str | None = None
    preferred_voice: str | None = None


@router.get("/profile")
async def get_profile(
    current_student: dict = Depends(get_current_student),
) -> dict:
    """Full student profile including scores, streak, and last topic."""
    return {
        "student_id": current_student["student_id"],
        "name": current_student["name"],
        "age": current_student.get("age"),
        "preferred_language": current_student.get("preferred_language", "en"),
        "preferred_voice": current_student.get("preferred_voice", "amelia"),
        "last_book": current_student.get("last_book"),
        "last_topic": current_student.get("last_topic"),
        "last_character": current_student.get("last_character"),
        "scores": current_student.get("scores", {}),
        "streak": current_student.get("streak", 0),
    }


@router.get("/progress")
async def get_progress(
    current_student: dict = Depends(get_current_student),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> dict:
    """Learning progress — scores, streak, and session count."""
    scores = current_student.get("scores", {})
    return {
        "knowledge_score": round(scores.get("knowledge", 0), 1),
        "enthusiasm_score": round(scores.get("enthusiasm", 50), 1),
        "pronunciation_score": round(scores.get("pronunciation", 50), 1),
        "total_interactions": scores.get("total_interactions", 0),
        "streak_days": current_student.get("streak", 0),
        "teaching_level": _get_level(scores.get("knowledge", 0)),
    }


@router.get("/pronunciation")
async def get_pronunciation_history(
    current_student: dict = Depends(get_current_student),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> dict:
    """Common pronunciation errors for this student."""
    errors = await mongo.get_common_errors(current_student["student_id"], limit=10)
    return {
        "common_errors": [
            {"word": e["_id"], "correct": e["correct"], "count": e["count"]}
            for e in errors
        ],
        "total_corrections": sum(e["count"] for e in errors),
    }


@router.patch("/preferences")
async def update_preferences(
    updates: PreferencesUpdate,
    current_student: dict = Depends(get_current_student),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> dict:
    """Update student language or voice preferences."""
    to_update = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not to_update:
        raise HTTPException(400, "No updates provided")
    await mongo.update_student(current_student["student_id"], to_update)
    return {"message": "Preferences updated", "updates": to_update}


def _get_level(knowledge: float) -> str:
    if knowledge < 30:
        return "beginner"
    elif knowledge < 70:
        return "intermediate"
    return "advanced"
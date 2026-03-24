"""
db/mongo_store.py — MongoDB Atlas for all student data.

Collections:
  students          → profile, scores, preferences, streak
  chat_sessions     → full conversation history per student
  pronunciation_log → mispronounced words + corrections
  learning_progress → per-topic and per-book progress
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
import motor.motor_asyncio
from pymongo import MongoClient, ASCENDING

logger = logging.getLogger(__name__)


class MongoStore:
    """Sync MongoDB client — used for admin/scripts."""

    def __init__(self, uri: str, db_name: str = "gyanadeva"):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.db.students.create_index("student_id", unique=True)
        self.db.students.create_index("email", unique=True)
        self.db.chat_sessions.create_index([("student_id", ASCENDING), ("created_at", ASCENDING)])
        self.db.pronunciation_log.create_index("student_id")
        self.db.learning_progress.create_index([("student_id", ASCENDING), ("book", ASCENDING)])
        logger.info("MongoDB indexes ensured")

    def close(self) -> None:
        self.client.close()


class AsyncMongoStore:
    """Async MongoDB client — used in FastAPI routes."""

    def __init__(self, uri: str, db_name: str = "gyanadeva"):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

    # ── Students ──────────────────────────────────────────────────

    async def create_student(self, student: dict) -> str:
        """Create a new student. Returns student_id."""
        student["created_at"] = datetime.now(timezone.utc)
        student["updated_at"] = datetime.now(timezone.utc)
        result = await self.db.students.insert_one(student)
        return str(result.inserted_id)

    async def get_student(self, student_id: str) -> dict | None:
        return await self.db.students.find_one(
            {"student_id": student_id}, {"_id": 0}
        )

    async def get_student_by_email(self, email: str) -> dict | None:
        return await self.db.students.find_one({"email": email}, {"_id": 0})

    async def update_student(self, student_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self.db.students.update_one(
            {"student_id": student_id},
            {"$set": updates},
        )

    # ── Chat Sessions ─────────────────────────────────────────────

    async def save_message(
        self,
        student_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Append a message to student's chat history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
            **(metadata or {}),
        }
        await self.db.chat_sessions.update_one(
            {"student_id": student_id},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )

    async def get_history(
        self, student_id: str, last_n: int = 20
    ) -> list[dict]:
        """Get last N messages for a student."""
        doc = await self.db.chat_sessions.find_one({"student_id": student_id})
        if not doc:
            return []
        messages = doc.get("messages", [])
        return messages[-last_n:]

    async def get_last_topic(self, student_id: str) -> dict | None:
        """Get what the student was last studying."""
        doc = await self.db.students.find_one(
            {"student_id": student_id},
            {"last_topic": 1, "last_book": 1, "last_character": 1},
        )
        return doc

    async def update_last_topic(
        self,
        student_id: str,
        book: str,
        topic: str,
        character: str | None = None,
    ) -> None:
        await self.db.students.update_one(
            {"student_id": student_id},
            {"$set": {
                "last_book": book,
                "last_topic": topic,
                "last_character": character,
                "last_active": datetime.now(timezone.utc),
            }},
        )

    # ── Scores & Progress ─────────────────────────────────────────

    async def update_scores(
        self,
        student_id: str,
        enthusiasm_delta: float = 0,
        knowledge_delta: float = 0,
    ) -> None:
        """Increment student scores after each interaction."""
        await self.db.students.update_one(
            {"student_id": student_id},
            {"$inc": {
                "scores.enthusiasm": enthusiasm_delta,
                "scores.knowledge": knowledge_delta,
                "scores.total_interactions": 1,
            }},
        )

    async def update_streak(self, student_id: str) -> int:
        """Update daily study streak. Returns current streak count."""
        student = await self.get_student(student_id)
        if not student:
            return 0

        now = datetime.now(timezone.utc)
        last_active = student.get("last_active")
        streak = student.get("streak", 0)

        if last_active:
            # Make last_active timezone-aware if it isn't (MongoDB stores UTC naive)
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            days_since = (now - last_active).days
            if days_since == 1:
                streak += 1
            elif days_since > 1:
                streak = 1  # reset streak
        else:
            streak = 1

        await self.db.students.update_one(
            {"student_id": student_id},
            {"$set": {"streak": streak, "last_active": now}},
        )
        return streak

    # ── Pronunciation ─────────────────────────────────────────────

    async def log_pronunciation_error(
        self,
        student_id: str,
        wrong_word: str,
        correct_word: str,
        context: str,
    ) -> None:
        """Log a pronunciation mistake for tracking."""
        await self.db.pronunciation_log.insert_one({
            "student_id": student_id,
            "wrong_word": wrong_word,
            "correct_word": correct_word,
            "context": context,
            "timestamp": datetime.now(timezone.utc),
            "corrected": False,
        })

    async def get_common_errors(
        self, student_id: str, limit: int = 5
    ) -> list[dict]:
        """Get most common pronunciation errors for a student."""
        pipeline = [
            {"$match": {"student_id": student_id}},
            {"$group": {
                "_id": "$wrong_word",
                "correct": {"$first": "$correct_word"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        cursor = self.db.pronunciation_log.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    def close(self) -> None:
        self.client.close()
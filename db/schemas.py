"""
db/schemas.py — MongoDB document schemas as TypedDicts.
Used for type hints and documentation throughout the project.
"""
from __future__ import annotations
from datetime import datetime
from typing import TypedDict, Optional


class StudentDoc(TypedDict):
    """MongoDB: students collection"""
    student_id: str          # UUID
    name: str
    email: str
    password_hash: str
    age: int
    preferred_language: str  # ISO code: hi, te, en...
    preferred_voice: str     # Sarvam voice name

    # Learning state
    last_book: str           # mahabharata | ramayana | bhagavad_gita
    last_topic: str
    last_character: Optional[str]
    last_active: datetime

    # Scores (0.0 - 100.0)
    scores: dict             # enthusiasm, knowledge, pronunciation, total_interactions

    # Streak
    streak: int              # consecutive days studied

    # Timestamps
    created_at: datetime
    updated_at: datetime


class MessageDoc(TypedDict):
    """Single message in a chat session"""
    role: str                # user | assistant
    content: str
    timestamp: datetime
    language: Optional[str]
    book_filter: Optional[str]
    sources: Optional[list]
    pronunciation_corrections: Optional[list]


class ChatSessionDoc(TypedDict):
    """MongoDB: chat_sessions collection"""
    student_id: str
    messages: list[MessageDoc]
    created_at: datetime
    updated_at: datetime


class PronunciationLogDoc(TypedDict):
    """MongoDB: pronunciation_log collection"""
    student_id: str
    wrong_word: str
    correct_word: str
    context: str
    timestamp: datetime
    corrected: bool


class LearningProgressDoc(TypedDict):
    """MongoDB: learning_progress collection"""
    student_id: str
    book: str
    topics_covered: list[str]
    characters_discussed: list[str]
    shlokas_read: int
    quiz_score: float
    updated_at: datetime


# ── Default student profile ────────────────────────────────────────

def default_student_scores() -> dict:
    return {
        "enthusiasm": 50.0,   # starts neutral
        "knowledge": 0.0,     # builds as they learn
        "pronunciation": 50.0, # starts neutral
        "total_interactions": 0,
    }


def new_student_doc(
    student_id: str,
    name: str,
    email: str,
    password_hash: str,
    age: int,
    preferred_language: str = "en",
) -> dict:
    """Create a fresh student document."""
    return {
        "student_id": student_id,
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "age": age,
        "preferred_language": preferred_language,
        "preferred_voice": "amelia",  # default warm voice
        "last_book": "bhagavad_gita",
        "last_topic": "introduction",
        "last_character": None,
        "last_active": None,
        "scores": default_student_scores(),
        "streak": 0,
    }

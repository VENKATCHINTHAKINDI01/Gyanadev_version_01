"""
memory/session_manager.py — The memory engine of the AI Guru.

Handles:
  - Resuming sessions from exactly where student left off
  - Building context from conversation history
  - Determining teaching style based on student profile
  - Generating the "welcome back" message
"""
from __future__ import annotations
import logging
from db.mongo_store import AsyncMongoStore

logger = logging.getLogger(__name__)

# How many history messages to inject into prompt
HISTORY_WINDOW = 10

BOOK_DISPLAY = {
    "mahabharata": "Mahabharata",
    "ramayana": "Ramayana",
    "bhagavad_gita": "Bhagavad Gita",
}


class SessionManager:
    """
    Manages student session continuity.
    The Guru never forgets where a student left off.
    """

    def __init__(self, mongo: AsyncMongoStore):
        self.mongo = mongo

    async def get_session_context(self, student_id: str) -> dict:
        """
        Build the full context the Guru needs before responding.

        Returns:
          - student profile (name, age, scores, language)
          - last topic / book / character
          - recent conversation history (last N turns)
          - pronunciation errors to watch for
          - teaching style level (1=beginner, 2=intermediate, 3=advanced)
        """
        student = await self.mongo.get_student(student_id)
        if not student:
            return {}

        history = await self.mongo.get_history(student_id, last_n=HISTORY_WINDOW)
        common_errors = await self.mongo.get_common_errors(student_id, limit=3)

        teaching_level = self._determine_level(student)

        return {
            "student": student,
            "history": history,
            "common_pronunciation_errors": common_errors,
            "teaching_level": teaching_level,
            "last_book": student.get("last_book", "bhagavad_gita"),
            "last_topic": student.get("last_topic", "introduction"),
            "last_character": student.get("last_character"),
        }

    async def get_welcome_back_message(self, student_id: str) -> str | None:
        """
        Generate a personalised welcome-back message.
        Called when student logs in (not on every message).
        Returns None if it's their first session.
        """
        student = await self.mongo.get_student(student_id)
        if not student or not student.get("last_active"):
            return None

        name = student["name"].split()[0]  # first name only
        last_book = BOOK_DISPLAY.get(student.get("last_book", ""), "the sacred texts")
        last_topic = student.get("last_topic", "")
        last_char = student.get("last_character")
        streak = student.get("streak", 0)

        streak_msg = ""
        if streak >= 7:
            streak_msg = f" You've been studying for {streak} days in a row — truly dedicated!"
        elif streak >= 3:
            streak_msg = f" {streak} days in a row — keep it up!"

        if last_char:
            return (
                f"Welcome back, {name}! 🙏 Last time we were learning about "
                f"{last_char} in the {last_book}. Shall we continue from there?{streak_msg}"
            )
        elif last_topic:
            return (
                f"Welcome back, {name}! 🙏 Last time we were studying {last_topic} "
                f"in the {last_book}. Ready to continue?{streak_msg}"
            )
        else:
            return f"Welcome back, {name}! 🙏 Ready to continue our journey?{streak_msg}"

    async def save_turn(
        self,
        student_id: str,
        user_message: str,
        assistant_response: str,
        book: str | None = None,
        topic: str | None = None,
        character: str | None = None,
        sources: list | None = None,
        language: str = "en",
    ) -> None:
        """Save one complete turn (user + assistant) to history."""
        await self.mongo.save_message(
            student_id=student_id,
            role="user",
            content=user_message,
            metadata={"language": language},
        )
        await self.mongo.save_message(
            student_id=student_id,
            role="assistant",
            content=assistant_response,
            metadata={
                "language": language,
                "sources": sources or [],
            },
        )

        # Update what they were last studying
        if book or topic or character:
            await self.mongo.update_last_topic(
                student_id=student_id,
                book=book or "general",
                topic=topic or "general",
                character=character,
            )

        # Update streak
        await self.mongo.update_streak(student_id)

    async def update_scores_after_turn(
        self,
        student_id: str,
        question_length: int,
        response_quality: float,
    ) -> None:
        """
        Update enthusiasm and knowledge scores after each interaction.
        - enthusiasm_delta: based on question length and depth
        - knowledge_delta: based on whether answer was grounded
        """
        # Longer, deeper questions = more enthusiasm
        enthusiasm_delta = min(2.0, question_length / 50)
        knowledge_delta = response_quality * 1.5  # 0-1.5 per interaction

        await self.mongo.update_scores(
            student_id=student_id,
            enthusiasm_delta=enthusiasm_delta,
            knowledge_delta=knowledge_delta,
        )

    @staticmethod
    def _determine_level(student: dict) -> int:
        """
        Determine teaching level from student's knowledge score.
        1 = beginner (0-30), 2 = intermediate (30-70), 3 = advanced (70+)
        """
        knowledge = student.get("scores", {}).get("knowledge", 0)
        if knowledge < 30:
            return 1
        elif knowledge < 70:
            return 2
        return 3

    @staticmethod
    def history_to_messages(history: list[dict]) -> list[dict]:
        """Convert MongoDB history to Groq message format."""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg.get("role") in ("user", "assistant")
        ]

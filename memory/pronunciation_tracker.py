"""
memory/pronunciation_tracker.py — Sanskrit/Hindu name pronunciation coach.

Detects mispronounced words in student's speech (from Sarvam STT transcript)
and instructs the Guru to correct them warmly, like a saint teaching a disciple.

Key insight: Sarvam STT may transcribe Sanskrit names phonetically as the
student pronounced them. We detect common variations and flag them.
"""
from __future__ import annotations
import re
import logging
from db.mongo_store import AsyncMongoStore

logger = logging.getLogger(__name__)

# ── Common mispronunciation patterns ─────────────────────────────
# Maps: what student likely said (regex) → correct pronunciation + phonetic guide

PRONUNCIATION_MAP = {
    # Mahabharata characters
    r"\barjoon\b|\barjun\b":          ("Arjuna", "Ar-ju-na"),
    r"\bkrishna\b|\bkrushna\b":       ("Krishna", "Krish-na"),
    r"\byudhishtir\b|\byudhistir\b":  ("Yudhishthira", "Yu-dhi-shth-i-ra"),
    r"\bdrona\b|\bdron\b":            ("Drona", "Dro-na"),
    r"\bbhishm\b|\bbhishma\b":        ("Bhishma", "Bheesh-ma"),
    r"\bdroopadi\b|\bdraupadi\b|\bdrupadi\b": ("Draupadi", "Drau-pa-di"),
    r"\bduryodhan\b|\bduryodhana\b":  ("Duryodhana", "Dur-yo-dha-na"),
    r"\bkarna\b|\bkaran\b":           ("Karna", "Kar-na"),
    r"\bbheem\b|\bbhima\b|\bbheem\b": ("Bhima", "Bhee-ma"),
    r"\bkunt[iy]\b":                  ("Kunti", "Kun-ti"),

    # Ramayana characters
    r"\brahma\b|\braam\b|\brama\b":   ("Rama", "Raa-ma"),
    r"\bsita\b|\bseeta\b":            ("Sita", "See-ta"),
    r"\blakshman\b|\blaxman\b":       ("Lakshmana", "Laksh-ma-na"),
    r"\bhanuaman\b|\bhanooman\b|\bhunuman\b": ("Hanuman", "Ha-nu-man"),
    r"\bravan\b|\bravana\b":          ("Ravana", "Ra-va-na"),
    r"\bdashrath\b|\bdasharath\b":    ("Dasharatha", "Da-sha-ra-tha"),
    r"\bkaikei\b|\bkaikeyi\b":        ("Kaikeyi", "Kai-ke-yi"),
    r"\bbharat\b|\bbharata\b":        ("Bharata", "Bha-ra-ta"),
    r"\bsugrib\b|\bsugreev\b":        ("Sugriva", "Su-gree-va"),

    # Gita / Sanskrit terms
    r"\bdharam\b|\bdharm\b":          ("Dharma", "Dhar-ma"),
    r"\bkarma\b|\bkarm\b":            ("Karma", "Kar-ma"),
    r"\bmoksh\b|\bmoksha\b":          ("Moksha", "Mok-sha"),
    r"\bgita\b|\bgeeta\b":            ("Bhagavad Gita", "Bha-ga-vad Gee-ta"),
    r"\bmahabhart\b|\bmahabharata\b": ("Mahabharata", "Ma-ha-bha-ra-ta"),
    r"\bramayn\b|\bramayana\b":       ("Ramayana", "Ra-ma-ya-na"),
    r"\bkurukshetr\b|\bkurukshetra\b":("Kurukshetra", "Ku-ru-kshe-tra"),
    r"\bayodhy\b|\bayodhya\b":        ("Ayodhya", "A-yodh-ya"),
    r"\blanka\b":                     ("Lanka", "Lan-ka"),
    r"\bartha\b|\barttha\b":          ("Artha", "Ar-tha"),
    r"\bkam\b|\bkama\b":              ("Kama", "Ka-ma"),
    r"\batman\b|\batma\b":            ("Atman", "Aat-man"),
    r"\bbrahman\b|\bbrahma\b":        ("Brahman", "Brah-man"),
    r"\byog\b|\byoga\b":              ("Yoga", "Yo-ga"),
    r"\bshlok\b|\bshloka\b":          ("Shloka", "Shlo-ka"),
}


class PronunciationCoach:
    """
    Detects mispronounced Sanskrit/Hindu names in student speech.
    Generates gentle correction instructions for the Guru's response.
    """

    def __init__(self, mongo: AsyncMongoStore):
        self.mongo = mongo

    def detect_errors(self, transcript: str) -> list[dict]:
        """
        Scan transcript for mispronounced words.
        Returns list of {wrong, correct, phonetic} dicts.
        """
        transcript_lower = transcript.lower()
        errors = []
        seen_corrections = set()

        for pattern, (correct, phonetic) in PRONUNCIATION_MAP.items():
            matches = re.findall(pattern, transcript_lower)
            if matches:
                wrong_word = matches[0]
                # Avoid duplicate corrections
                if correct not in seen_corrections:
                    errors.append({
                        "wrong": wrong_word,
                        "correct": correct,
                        "phonetic": phonetic,
                    })
                    seen_corrections.add(correct)

        return errors

    async def log_and_build_correction(
        self,
        student_id: str,
        transcript: str,
        student_name: str,
    ) -> str | None:
        """
        Detect errors, log them, and return a correction instruction
        for the Guru's system prompt (or None if no errors).
        """
        errors = self.detect_errors(transcript)
        if not errors:
            return None

        # Log each error
        for err in errors:
            await self.mongo.log_pronunciation_error(
                student_id=student_id,
                wrong_word=err["wrong"],
                correct_word=err["correct"],
                context=transcript[:200],
            )

        # Build gentle correction instruction for the Guru
        corrections = []
        for err in errors[:2]:  # max 2 corrections per turn — don't overwhelm
            corrections.append(
                f"The student said '{err['wrong']}' — gently correct to '{err['correct']}' "
                f"(pronounced: {err['phonetic']}) in a warm, encouraging way."
            )

        instruction = (
            "PRONUNCIATION NOTE: " + " Also, ".join(corrections) +
            " Weave the correction naturally into your response, like a loving guru — "
            "never make the student feel embarrassed."
        )
        logger.info(f"Pronunciation correction for {student_name}: {[e['wrong'] for e in errors]}")
        return instruction

    @staticmethod
    def build_correction_message(errors: list[dict], student_name: str) -> str:
        """
        Build a warm, saint-like correction message to append to the response.
        """
        if not errors:
            return ""

        first_name = student_name.split()[0]
        if len(errors) == 1:
            err = errors[0]
            return (
                f"\n\n✨ *By the way, {first_name}-ji* — the name is pronounced "
                f"**{err['correct']}** ({err['phonetic']}). "
                f"Try saying it slowly with me! 🙏"
            )
        else:
            corrections = ", ".join(
                f"**{e['correct']}** ({e['phonetic']})" for e in errors[:2]
            )
            return (
                f"\n\n✨ *A gentle note, {first_name}-ji* — "
                f"the correct pronunciations are: {corrections}. "
                f"Practice makes perfect! 🙏"
            )

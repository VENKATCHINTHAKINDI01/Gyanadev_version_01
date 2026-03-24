"""
rag/guardrails.py — Anti-hallucination and safety guardrails.

Layer 1: Scope detection — block off-topic questions
Layer 2: Faithfulness  — verify answer is grounded in context
Layer 3: Child safety  — flag inappropriate content
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyVerdict(str, Enum):
    PASS         = "pass"
    OUT_OF_SCOPE = "out_of_scope"
    UNFAITHFUL   = "unfaithful"
    UNSAFE       = "unsafe"


@dataclass
class GuardrailResult:
    verdict:           SafetyVerdict
    is_safe:           bool
    faithfulness_score:float
    reason:            str
    safe_fallback:     str | None = None


EPIC_KEYWORDS = {
    "arjuna","krishna","yudhishthira","bhima","nakula","sahadeva",
    "draupadi","duryodhana","bhishma","drona","karna","kunti",
    "rama","sita","lakshmana","hanuman","ravana","bharata",
    "dasharatha","sugriva","vibhishana","jatayu","mandodari",
    "mahabharata","ramayana","bhagavad gita","gita","mahabharat",
    "dharma","karma","moksha","kurukshetra","lanka","ayodhya",
    "pandava","kaurava","kshatriya","brahmin","yagna","yoga",
    "atman","brahman","vishnu","shloka","parva","kanda",
    "ashram","avatar","deva","asura","gandiva","pashupatastra",
}

NON_EPIC_WORDS = {
    "pizza","recipe","cook","cooking","food","restaurant",
    "movie","film","song","cricket","football","sport","soccer",
    "dinosaur","fossil","napoleon","einstein","shakespeare",
    "physics","chemistry","biology","math","algebra",
    "computer","internet","robot","smartphone",
    "country","capital","continent","ocean",
    "france","germany","italy","england","usa","russia","china","japan",
    "president","parliament","election","democracy",
}

NOT_FOUND_PHRASES = [
    "not covered in our texts",
    "i could not find",
    "this is not mentioned",
    "not in the context",
    "ask me about",
]

UNSAFE_PATTERNS = [
    r"\b(sex|sexual|nude|naked)\b",
    r"\b(murder|gore|torture)\b",
    r"\b(drug|alcohol|drunk|intoxicat)\b",
]

QUESTION_PATTERNS = [
    r"\bwho\s+(is|was|are|were)\b",
    r"\btell\s+me\s+about\b",
    r"\bwhat\s+happened\b",
    r"\bwhy\s+did\b",
    r"\bhow\s+did\b",
    r"\bwhat\s+did\b",
    r"\bstory\s+of\b",
    r"\bexplain\b",
    r"\bdescribe\b",
]


class Guardrails:
    def __init__(self, min_faithfulness: float = 0.5):
        self.min_faithfulness = min_faithfulness

    # ── Layer 1: Scope ────────────────────────────────────────────

    def is_in_scope(self, query: str) -> bool:
        q = query.lower()
        # Epic keyword → always in scope
        if any(kw in q for kw in EPIC_KEYWORDS):
            return True
        # Non-epic word → block
        if any(w in q for w in NON_EPIC_WORDS):
            return False
        # Numeric expression → block
        if re.search(r"\d+\s*[+\-*/]\s*\d+", q):
            return False
        # General question structure → allow (retrieval handles empty results)
        if any(re.search(p, q) for p in QUESTION_PATTERNS):
            return True
        return False

    def out_of_scope_message(self, language: str = "en") -> str:
        messages = {
            "en": "That question is outside our texts today. Ask me about Arjuna, Rama, Hanuman, Krishna, or the Bhagavad Gita! 🙏",
            "hi": "यह प्रश्न हमारे ग्रंथों में नहीं है। अर्जुन, राम, हनुमान या भगवद गीता के बारे में पूछें! 🙏",
            "te": "ఆ ప్రశ్న మన గ్రంథాలలో లేదు. అర్జున, రాముడు లేదా హనుమంతుడి గురించి అడగండి! 🙏",
        }
        return messages.get(language, messages["en"])

    # ── Layer 2: Faithfulness ─────────────────────────────────────

    def check_faithfulness(
        self, query: str, answer: str, context_chunks: list[str]
    ) -> GuardrailResult:
        if not answer.strip():
            return GuardrailResult(SafetyVerdict.PASS, True, 1.0, "Empty answer")

        # Not-found phrases always safe
        a_lower = answer.lower()
        if any(p in a_lower for p in NOT_FOUND_PHRASES):
            return GuardrailResult(SafetyVerdict.PASS, True, 1.0, "Safe not-found response")

        if not context_chunks:
            return GuardrailResult(
                SafetyVerdict.UNFAITHFUL, False, 0.0,
                "No context provided",
                safe_fallback=self._no_answer_msg(),
            )

        # Simple keyword overlap check (NLI model optional)
        score = self._keyword_faithfulness(answer, context_chunks)

        if score >= self.min_faithfulness:
            return GuardrailResult(SafetyVerdict.PASS, True, score, f"Score {score:.2f}")

        logger.warning(f"Low faithfulness: {score:.2f}")
        return GuardrailResult(
            SafetyVerdict.UNFAITHFUL, False, score,
            f"Answer score {score:.2f} below threshold {self.min_faithfulness}",
            safe_fallback=self._no_answer_msg(),
        )

    # ── Layer 3: Child Safety ─────────────────────────────────────

    def has_unsafe_content(self, text: str) -> bool:
        t = text.lower()
        return any(re.search(p, t) for p in UNSAFE_PATTERNS)

    def get_age_prompt(self, level: int) -> str:
        return {
            1: "Use very simple words and short sentences, like a bedtime story for a 7-year-old.",
            2: "Use clear language suitable for an 11-year-old. Explain Sanskrit words.",
            3: "You may include philosophical depth. Suitable for a 14-year-old.",
        }.get(max(1, min(3, level)), "Use clear, simple language.")

    # ── Private ───────────────────────────────────────────────────

    @staticmethod
    def _keyword_faithfulness(answer: str, chunks: list[str]) -> float:
        """
        Lightweight faithfulness check: what fraction of answer words
        appear in the context? No external model needed.
        """
        context_text = " ".join(chunks).lower()
        context_words = set(re.findall(r"\b\w{4,}\b", context_text))

        answer_words = re.findall(r"\b\w{4,}\b", answer.lower())
        if not answer_words:
            return 1.0

        # Exclude common stop words from check
        stop_words = {
            "that","this","with","from","have","been","will","they",
            "were","said","also","when","then","thus","their","which",
            "these","those","there","would","could","should","about",
        }
        factual = [w for w in answer_words if w not in stop_words]
        if not factual:
            return 1.0

        overlap = sum(1 for w in factual if w in context_words)
        return overlap / len(factual)

    @staticmethod
    def _no_answer_msg() -> str:
        return (
            "I could not find the answer to that in our texts today. "
            "Try asking about a specific character or story from the "
            "Mahabharata, Ramayana, or Bhagavad Gita! 🙏"
        )
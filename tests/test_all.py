"""
tests/test_all.py — Complete test suite for GyanaDev.
Run: pytest tests/ -v
"""
import sys, types, unittest.mock as mock
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# ── Mock all external deps so tests run without installing them ────
pymongo_mod = types.ModuleType("pymongo")
pymongo_mod.MongoClient = MagicMock()
pymongo_mod.ASCENDING = 1
pymongo_mod.DESCENDING = -1
pymongo_mod.UpdateOne = MagicMock()
errors_mod = types.ModuleType("pymongo.errors")
errors_mod.BulkWriteError = type("BulkWriteError", (Exception,), {"details": {}})
pymongo_mod.errors = errors_mod

motor_mod = types.ModuleType("motor")
motor_async_mod = types.ModuleType("motor.motor_asyncio")
motor_async_mod.AsyncIOMotorClient = MagicMock()
motor_mod.motor_asyncio = motor_async_mod

sys.modules.update({
    "pymongo": pymongo_mod,
    "pymongo.errors": errors_mod,
    "motor": motor_mod,
    "motor.motor_asyncio": motor_async_mod,
    "groq": MagicMock(),
    "qdrant_client": MagicMock(),
    "qdrant_client.models": MagicMock(),
    "rank_bm25": MagicMock(),
    "langdetect": MagicMock(),
    "structlog": MagicMock(),
    "aiohttp": MagicMock(),
    "requests": MagicMock(),
    "pydub": MagicMock(),
    "jose": MagicMock(),
    "jose.jwt": MagicMock(),
    "passlib": MagicMock(),
    "passlib.context": MagicMock(),
})

# ══════════════════════════════════════════════════════════════════
# 1. CHUNKER TESTS
# ══════════════════════════════════════════════════════════════════

class TestShlokaChunker:

    def setup_method(self):
        from ingestion.chunker import ShlokaChunker, Book
        self.chunker = ShlokaChunker(target_tokens=200, overlap_verses=1)
        self.Book = Book

    def test_gita_chunks_generated(self):
        text = "\n".join([
            f"{i}. Arjuna asked Krishna about dharma and the eternal soul at Kurukshetra."
            for i in range(1, 15)
        ])
        chunks = self.chunker.chunk_book(text, self.Book.BHAGAVAD_GITA, 1, "Chapter 1")
        assert len(chunks) > 0

    def test_chunk_has_required_fields(self):
        text = "\n".join([f"{i}. Rama is the prince of Ayodhya." for i in range(1, 10)])
        chunks = self.chunker.chunk_book(text, self.Book.RAMAYANA, 1, "Bala Kanda")
        assert chunks
        c = chunks[0]
        assert c.chunk_id
        assert c.text
        assert c.source_citation
        assert c.book == self.Book.RAMAYANA

    def test_character_tagging_arjuna(self):
        text = "1. Arjuna raised his Gandiva bow. 2. Krishna smiled at Arjuna warmly."
        chunks = self.chunker.chunk_book(text, self.Book.BHAGAVAD_GITA, 1, "Chapter 1")
        all_chars = {c for chunk in chunks for c in chunk.characters}
        assert "Arjuna" in all_chars
        assert "Krishna" in all_chars

    def test_character_tagging_ramayana(self):
        text = "1. Hanuman leaped across the ocean. 2. Sita waited in Lanka. 3. Rama searched everywhere."
        chunks = self.chunker.chunk_book(text, self.Book.RAMAYANA, 5, "Sundara Kanda")
        all_chars = {c for chunk in chunks for c in chunk.characters}
        assert "Hanuman" in all_chars

    def test_topic_tagging_dharma(self):
        text = "1. Yudhishthira spoke of dharma and righteousness above all else."
        chunks = self.chunker.chunk_book(text, self.Book.MAHABHARATA, 1, "Adi Parva")
        all_topics = {t for chunk in chunks for t in chunk.topics}
        assert "dharma" in all_topics

    def test_topic_tagging_war(self):
        text = "1. The great battle at Kurukshetra began with warriors and weapons."
        chunks = self.chunker.chunk_book(text, self.Book.MAHABHARATA, 6, "Bhishma Parva")
        all_topics = {t for chunk in chunks for t in chunk.topics}
        assert "war" in all_topics

    def test_chunk_id_deterministic(self):
        text = "1. Krishna taught the Bhagavad Gita to Arjuna on the battlefield."
        c1 = self.chunker.chunk_book(text, self.Book.BHAGAVAD_GITA, 1, "Chapter 1")
        c2 = self.chunker.chunk_book(text, self.Book.BHAGAVAD_GITA, 1, "Chapter 1")
        assert [x.chunk_id for x in c1] == [x.chunk_id for x in c2]

    def test_citation_format_gita(self):
        text = "1. Arjuna said to Krishna: O Lord, I am confused about my duty."
        chunks = self.chunker.chunk_book(text, self.Book.BHAGAVAD_GITA, 2, "Chapter 2")
        assert chunks
        assert "Bhagavad Gita" in chunks[0].source_citation
        assert "Chapter 2" in chunks[0].source_citation

    def test_citation_format_mahabharata(self):
        text = "1. Bhishma stood as commander of the Kaurava forces."
        chunks = self.chunker.chunk_book(text, self.Book.MAHABHARATA, 6, "Bhishma Parva")
        assert chunks
        assert "Mahabharata" in chunks[0].source_citation
        assert "Bhishma Parva" in chunks[0].source_citation

    def test_to_dict_schema(self):
        text = "1. Sita was found by King Janaka while plowing the sacred earth."
        chunks = self.chunker.chunk_book(text, self.Book.RAMAYANA, 1, "Bala Kanda")
        assert chunks
        d = chunks[0].to_dict()
        required = ["chunk_id","text","book","section_number","section_name",
                    "characters","topics","token_count","source_citation"]
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_overlap_produces_multiple_chunks(self):
        from ingestion.chunker import ShlokaChunker
        chunker = ShlokaChunker(target_tokens=80, overlap_verses=1)
        text = "\n".join([f"{i}. Long verse about dharma karma yoga moksha atman brahman wisdom." for i in range(1, 20)])
        chunks = chunker.chunk_book(text, self.Book.BHAGAVAD_GITA, 1, "Chapter 1")
        assert len(chunks) >= 2

    def test_all_three_books_chunk(self):
        texts = {
            self.Book.MAHABHARATA:  "1. Arjuna fought at Kurukshetra. 2. Bhima defeated Duryodhana.",
            self.Book.RAMAYANA:     "1. Rama rescued Sita. 2. Hanuman burned Lanka.",
            self.Book.BHAGAVAD_GITA:"1. Krishna spoke of dharma. 2. Arjuna listened carefully.",
        }
        from ingestion.chunker import get_section_map
        for book, text in texts.items():
            sec_map = get_section_map(book)
            sec_name = list(sec_map.values())[0]
            chunks = self.chunker.chunk_book(text, book, 1, sec_name)
            assert len(chunks) > 0, f"No chunks for {book}"

    def test_section_maps_all_books(self):
        from ingestion.chunker import Book, get_section_map
        assert len(get_section_map(Book.MAHABHARATA)) == 18
        assert len(get_section_map(Book.RAMAYANA)) == 7
        assert len(get_section_map(Book.BHAGAVAD_GITA)) == 18


# ══════════════════════════════════════════════════════════════════
# 2. GUARDRAILS TESTS
# ══════════════════════════════════════════════════════════════════

class TestGuardrails:

    def setup_method(self):
        from rag.guardrails import Guardrails, SafetyVerdict
        self.g = Guardrails(min_faithfulness=0.3)
        self.SafetyVerdict = SafetyVerdict

    # ── Scope detection ──────────────────────────────────────────

    def test_in_scope_epic_keywords(self):
        for q in ["Who is Arjuna?", "Tell me about Hanuman", "What is dharma?",
                  "Who is Ravana?", "What is karma?", "Tell me about Krishna"]:
            assert self.g.is_in_scope(q), f"Should be in scope: {q!r}"

    def test_out_of_scope_non_epic(self):
        for q in ["How do I make pizza?", "What is 2+2?", "Tell me about dinosaurs",
                  "What is the capital of France?", "Tell me about cricket",
                  "Who is Einstein?", "How do I cook rice?"]:
            assert not self.g.is_in_scope(q), f"Should be out of scope: {q!r}"

    def test_in_scope_ramayana_characters(self):
        assert self.g.is_in_scope("Tell me about Sita")
        assert self.g.is_in_scope("Who is Lakshmana?")
        assert self.g.is_in_scope("What did Vibhishana do?")

    def test_in_scope_mahabharata_events(self):
        assert self.g.is_in_scope("What happened at Kurukshetra?")
        assert self.g.is_in_scope("Tell me about the Pandavas")
        assert self.g.is_in_scope("Who is Duryodhana?")

    def test_in_scope_gita_concepts(self):
        assert self.g.is_in_scope("What is moksha?")
        assert self.g.is_in_scope("Explain yoga")
        assert self.g.is_in_scope("What is atman?")

    # ── Faithfulness ─────────────────────────────────────────────

    def test_not_found_phrase_always_safe(self):
        for phrase in [
            "not covered in our texts today",
            "I could not find the answer",
            "this is not mentioned in the context",
            "ask me about the Mahabharata",
        ]:
            r = self.g.check_faithfulness("q?", phrase, [])
            assert r.is_safe, f"Not-found phrase should be safe: {phrase!r}"

    def test_no_context_fails(self):
        r = self.g.check_faithfulness("Who is Arjuna?", "Arjuna was a great warrior.", [])
        assert not r.is_safe
        assert r.verdict == self.SafetyVerdict.UNFAITHFUL

    def test_empty_answer_passes(self):
        r = self.g.check_faithfulness("q?", "", ["some context here"])
        assert r.is_safe

    def test_grounded_answer_passes(self):
        ctx = ["Arjuna was the third Pandava, son of Kunti and the wind god Vayu."]
        ans = "Arjuna was the third Pandava born to Kunti. He was a great warrior."
        r = self.g.check_faithfulness("Who is Arjuna?", ans, ctx)
        assert r.is_safe

    def test_faithfulness_score_range(self):
        ctx = ["Krishna spoke of dharma on the battlefield of Kurukshetra to Arjuna."]
        ans = "Krishna spoke about dharma to Arjuna at Kurukshetra battlefield."
        r = self.g.check_faithfulness("What did Krishna say?", ans, ctx)
        assert 0.0 <= r.faithfulness_score <= 1.0

    # ── Child safety ─────────────────────────────────────────────

    def test_safe_epic_content(self):
        for t in [
            "Arjuna fought bravely at Kurukshetra.",
            "Rama rescued Sita from Ravana.",
            "Krishna taught the Bhagavad Gita.",
            "Hanuman burned the city of Lanka.",
        ]:
            assert not self.g.has_unsafe_content(t), f"Should be safe: {t!r}"

    def test_unsafe_content_flagged(self):
        assert self.g.has_unsafe_content("explicit sexual content")
        assert self.g.has_unsafe_content("she was naked and drunk")

    def test_age_prompts_all_levels(self):
        for level in [1, 2, 3]:
            prompt = self.g.get_age_prompt(level)
            assert isinstance(prompt, str)
            assert len(prompt) > 10

    def test_out_of_scope_message_english(self):
        msg = self.g.out_of_scope_message("en")
        assert isinstance(msg, str)
        assert len(msg) > 20

    def test_out_of_scope_message_hindi(self):
        msg = self.g.out_of_scope_message("hi")
        assert isinstance(msg, str)
        assert len(msg) > 10


# ══════════════════════════════════════════════════════════════════
# 3. LANGUAGE DETECTION TESTS
# ══════════════════════════════════════════════════════════════════

class TestLanguageDetector:

    def setup_method(self):
        from multilingual.sarvam import LanguageDetector
        self.d = LanguageDetector()

    def test_hindi_devanagari(self):
        assert self.d._detect_by_script("अर्जुन कौन है?") == "hi"

    def test_telugu(self):
        assert self.d._detect_by_script("అర్జుని ఎవరు?") == "te"

    def test_tamil(self):
        assert self.d._detect_by_script("அர்ஜுன் யார்?") == "ta"

    def test_kannada(self):
        assert self.d._detect_by_script("ಅರ್ಜುನ ಯಾರು?") == "kn"

    def test_malayalam(self):
        assert self.d._detect_by_script("അർജുൻ ആരാണ്?") == "ml"

    def test_bengali(self):
        assert self.d._detect_by_script("অর্জুন কে?") == "bn"

    def test_gujarati(self):
        assert self.d._detect_by_script("અર્જુન કોણ છે?") == "gu"

    def test_punjabi(self):
        assert self.d._detect_by_script("ਅਰਜੁਨ ਕੌਣ ਹੈ?") == "pa"

    def test_odia(self):
        assert self.d._detect_by_script("ଅର୍ଜୁନ କିଏ?") == "or"

    def test_english_returns_none(self):
        assert self.d._detect_by_script("Who is Arjuna?") is None


# ══════════════════════════════════════════════════════════════════
# 4. PRONUNCIATION TRACKER TESTS
# ══════════════════════════════════════════════════════════════════

class TestPronunciationTracker:

    def setup_method(self):
        from memory.pronunciation_tracker import PronunciationCoach
        mock_mongo = MagicMock()
        mock_mongo.log_pronunciation_error = AsyncMock()
        self.coach = PronunciationCoach(mongo=mock_mongo)

    def test_detects_arjuna_mispronunciation(self):
        errors = self.coach.detect_errors("Tell me about arjoon")
        assert any(e["correct"] == "Arjuna" for e in errors)

    def test_detects_hanuman_mispronunciation(self):
        errors = self.coach.detect_errors("What did hanooman do?")
        assert any(e["correct"] == "Hanuman" for e in errors)

    def test_detects_draupadi_mispronunciation(self):
        errors = self.coach.detect_errors("Who is droopadi?")
        assert any(e["correct"] == "Draupadi" for e in errors)

    def test_detects_dharma_mispronunciation(self):
        errors = self.coach.detect_errors("What is dharam?")
        assert any(e["correct"] == "Dharma" for e in errors)

    def test_detects_ramayana_mispronunciation(self):
        errors = self.coach.detect_errors("Tell me about the ramayn")
        assert any(e["correct"] == "Ramayana" for e in errors)

    def test_no_errors_correct_spelling(self):
        errors = self.coach.detect_errors("Tell me about Arjuna and Krishna")
        assert len(errors) == 0

    def test_correction_message_single_error(self):
        errors = [{"wrong": "arjoon", "correct": "Arjuna", "phonetic": "Ar-ju-na"}]
        msg = self.coach.build_correction_message(errors, "Rahul Kumar")
        assert "Arjuna" in msg
        assert "Ar-ju-na" in msg
        assert "Rahul" in msg

    def test_correction_message_empty(self):
        msg = self.coach.build_correction_message([], "Priya")
        assert msg == ""

    def test_phonetic_guide_present(self):
        errors = self.coach.detect_errors("Who is yudhishtir?")
        yudhi = [e for e in errors if "Yudhishthira" in e["correct"]]
        if yudhi:
            assert yudhi[0]["phonetic"]


# ══════════════════════════════════════════════════════════════════
# 5. SARVAM VOICE TESTS (mocked)
# ══════════════════════════════════════════════════════════════════

class TestSarvamTTS:

    def test_text_chunking_short(self):
        from multilingual.sarvam import SarvamTTS
        t = "Rama is the prince of Ayodhya."
        assert SarvamTTS._chunk_text(t) == [t]

    def test_text_chunking_long(self):
        from multilingual.sarvam import SarvamTTS
        long = "Arjuna was a great warrior who fought at Kurukshetra. " * 60
        chunks = SarvamTTS._chunk_text(long, max_chars=2500)
        assert len(chunks) > 1
        assert all(len(c) <= 2500 for c in chunks)

    def test_text_chunking_hindi(self):
        from multilingual.sarvam import SarvamTTS
        hindi = "श्री भगवान ने कहा। अर्जुन महान वीर था। धर्म की जीत हुई।"
        chunks = SarvamTTS._chunk_text(hindi, max_chars=40)
        assert len(chunks) >= 2

    def test_language_codes_mapping(self):
        from multilingual.sarvam import ISO_TO_BCP47, BCP47_TO_ISO
        assert ISO_TO_BCP47["hi"] == "hi-IN"
        assert ISO_TO_BCP47["te"] == "te-IN"
        assert ISO_TO_BCP47["or"] == "od-IN"
        assert BCP47_TO_ISO["hi-IN"] == "hi"
        assert BCP47_TO_ISO["te-IN"] == "te"

    def test_default_voices_present(self):
        from multilingual.sarvam import DEFAULT_VOICES
        assert DEFAULT_VOICES["hi"] == "ritu"
        assert DEFAULT_VOICES["te"] == "pavithra"
        assert DEFAULT_VOICES["ta"] == "maitreyi"
        assert "en" in DEFAULT_VOICES

    def test_tts_supported_languages(self):
        from multilingual.sarvam import TTS_SUPPORTED
        for lang in ["hi", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or", "en"]:
            assert lang in TTS_SUPPORTED


# ══════════════════════════════════════════════════════════════════
# 6. GURU TEACHER TESTS
# ══════════════════════════════════════════════════════════════════

class TestGuruTeacher:

    def setup_method(self):
        from guru.teacher import Guru
        mock_groq = MagicMock()
        mock_groq.generate_with_history.return_value = "Arjuna was a great archer. 📖 From: Mahabharata — Adi Parva"
        self.guru = Guru(groq_client=mock_groq)

    def test_system_prompt_contains_rules(self):
        from guru.teacher import GURU_SYSTEM_PROMPT, AGE_INSTRUCTIONS, LEVEL_INSTRUCTIONS
        prompt = GURU_SYSTEM_PROMPT.format(
            level_instruction=LEVEL_INSTRUCTIONS[2],
            student_name="Arjun",
            student_age=12,
            knowledge_score=30,
            enthusiasm_score=60,
            streak=3,
            last_topic="dharma",
            last_book="the Bhagavad Gita",
            first_name="Arjun",
            pronunciation_note="",
            context_passages="[Passage 1]\nSource: Test\nText: Arjuna was brave.",
        )
        assert "ONLY" in prompt
        assert "CONTEXT PASSAGES" in prompt
        assert "📖 From:" in prompt
        assert "never" in prompt.lower() or "Never" in prompt

    def test_format_context_with_chunks(self):
        mock_chunk = MagicMock()
        mock_chunk.source_citation = "Bhagavad Gita — Chapter 1"
        mock_chunk.text = "Arjuna stood on the battlefield."
        result = self.guru.format_context([mock_chunk])
        assert "Bhagavad Gita" in result
        assert "Arjuna" in result

    def test_format_context_empty(self):
        result = self.guru.format_context([])
        assert "No relevant passages" in result

    def test_response_quality_with_citation(self):
        ans = "Arjuna was a great warrior who fought bravely. 📖 From: Mahabharata — Chapter 1"
        score = self.guru.estimate_response_quality(ans)
        assert score > 0.5

    def test_response_quality_fallback_low(self):
        ans = "not covered in our texts today, dear student"
        score = self.guru.estimate_response_quality(ans)
        assert score < 0.3

    def test_response_quality_no_citation(self):
        ans = "Arjuna was brave but there is no source citation here"
        score = self.guru.estimate_response_quality(ans)
        assert score == 0.3

    def test_teaching_levels_defined(self):
        from guru.teacher import LEVEL_INSTRUCTIONS
        assert 1 in LEVEL_INSTRUCTIONS
        assert 2 in LEVEL_INSTRUCTIONS
        assert 3 in LEVEL_INSTRUCTIONS
        for level, text in LEVEL_INSTRUCTIONS.items():
            assert len(text) > 20


# ══════════════════════════════════════════════════════════════════
# 7. SESSION MANAGER TESTS
# ══════════════════════════════════════════════════════════════════

class TestSessionManager:

    def test_determine_level_beginner(self):
        from memory.session_manager import SessionManager
        student = {"scores": {"knowledge": 10}}
        assert SessionManager._determine_level(student) == 1

    def test_determine_level_intermediate(self):
        from memory.session_manager import SessionManager
        student = {"scores": {"knowledge": 50}}
        assert SessionManager._determine_level(student) == 2

    def test_determine_level_advanced(self):
        from memory.session_manager import SessionManager
        student = {"scores": {"knowledge": 80}}
        assert SessionManager._determine_level(student) == 3

    def test_determine_level_zero(self):
        from memory.session_manager import SessionManager
        student = {"scores": {"knowledge": 0}}
        assert SessionManager._determine_level(student) == 1

    def test_history_to_messages(self):
        from memory.session_manager import SessionManager
        history = [
            {"role": "user", "content": "Who is Arjuna?", "timestamp": "2024-01-01"},
            {"role": "assistant", "content": "Arjuna is the third Pandava.", "timestamp": "2024-01-01"},
            {"role": "system", "content": "ignored", "timestamp": "2024-01-01"},
        ]
        messages = SessionManager.history_to_messages(history)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert "timestamp" not in messages[0]

    def test_book_display_names(self):
        from memory.session_manager import BOOK_DISPLAY
        assert BOOK_DISPLAY["mahabharata"] == "Mahabharata"
        assert BOOK_DISPLAY["ramayana"] == "Ramayana"
        assert BOOK_DISPLAY["bhagavad_gita"] == "Bhagavad Gita"


# ══════════════════════════════════════════════════════════════════
# 8. AUTH TESTS
# ══════════════════════════════════════════════════════════════════

class TestAuth:

    def test_generate_student_id_is_uuid(self):
        from auth.models import generate_student_id
        import re
        sid = generate_student_id()
        assert re.match(r"[0-9a-f-]{36}", sid)

    def test_generate_student_id_unique(self):
        from auth.models import generate_student_id
        ids = {generate_student_id() for _ in range(10)}
        assert len(ids) == 10

    def test_password_hash_and_verify(self):
        with patch("auth.models.pwd_context") as mock_ctx:
            mock_ctx.hash.return_value = "hashed_pw"
            mock_ctx.verify.return_value = True
            from auth.models import hash_password, verify_password
            hashed = hash_password("secret123")
            assert verify_password("secret123", hashed)

    def test_new_student_doc_structure(self):
        from db.schemas import new_student_doc, default_student_scores
        doc = new_student_doc("id1", "Arjun", "arjun@test.com", "hash", 12, "hi")
        assert doc["student_id"] == "id1"
        assert doc["name"] == "Arjun"
        assert doc["age"] == 12
        assert doc["preferred_language"] == "hi"
        assert "scores" in doc
        assert doc["streak"] == 0

    def test_default_scores_structure(self):
        from db.schemas import default_student_scores
        s = default_student_scores()
        assert "knowledge" in s
        assert "enthusiasm" in s
        assert "pronunciation" in s
        assert "total_interactions" in s
        assert s["knowledge"] == 0.0
        assert s["enthusiasm"] == 50.0


# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
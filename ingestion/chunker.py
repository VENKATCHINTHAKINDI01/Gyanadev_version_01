"""
ingestion/chunker.py — Shloka-aware text chunker for Hindu epics.

Strategy:
  - Split at verse/shloka boundaries — never mid-sentence
  - Attach rich metadata to every chunk (book, section, verse, characters, topics)
  - Deterministic chunk IDs (content hash) for safe re-ingestion
  - Overlap 2 verses between chunks for context continuity
"""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum


class Book(str, Enum):
    MAHABHARATA  = "mahabharata"
    RAMAYANA     = "ramayana"
    BHAGAVAD_GITA = "bhagavad_gita"


SECTION_NAMES = {
    Book.MAHABHARATA: {
        1:"Adi Parva", 2:"Sabha Parva", 3:"Vana Parva", 4:"Virata Parva",
        5:"Udyoga Parva", 6:"Bhishma Parva", 7:"Drona Parva", 8:"Karna Parva",
        9:"Shalya Parva", 10:"Sauptika Parva", 11:"Stri Parva", 12:"Shanti Parva",
        13:"Anushasana Parva", 14:"Ashvamedhika Parva", 15:"Ashramavasika Parva",
        16:"Mausala Parva", 17:"Mahaprasthanika Parva", 18:"Svargarohana Parva",
    },
    Book.RAMAYANA: {
        1:"Bala Kanda", 2:"Ayodhya Kanda", 3:"Aranya Kanda",
        4:"Kishkindha Kanda", 5:"Sundara Kanda", 6:"Yuddha Kanda", 7:"Uttara Kanda",
    },
    Book.BHAGAVAD_GITA: {i: f"Chapter {i}" for i in range(1, 19)},
}

CHARACTERS = {
    Book.MAHABHARATA: [
        "Arjuna","Krishna","Yudhishthira","Bhima","Nakula","Sahadeva",
        "Draupadi","Duryodhana","Bhishma","Drona","Karna","Kunti",
        "Dhritarashtra","Pandu","Ashwatthama","Vyasa","Gandhari",
    ],
    Book.RAMAYANA: [
        "Rama","Sita","Lakshmana","Hanuman","Ravana","Bharata",
        "Shatrughna","Dasharatha","Kaikeyi","Kaushalya","Sugriva",
        "Vali","Vibhishana","Jatayu","Mandodari",
    ],
    Book.BHAGAVAD_GITA: ["Arjuna","Krishna","Dhritarashtra","Sanjaya"],
}

TOPIC_KEYWORDS = {
    "dharma":    ["dharma","duty","righteousness","righteous"],
    "war":       ["battle","war","warrior","army","weapon","bow","fight"],
    "devotion":  ["devotion","bhakti","worship","prayer","divine","god"],
    "wisdom":    ["wisdom","knowledge","truth","teach","lesson","philosophy"],
    "exile":     ["exile","forest","banishment","wander","vanvas"],
    "love":      ["love","marriage","wife","husband"],
    "karma":     ["karma","action","deed","fruit","result"],
    "moksha":    ["liberation","moksha","salvation","soul","atman"],
    "sacrifice": ["sacrifice","yagna","offering","ritual"],
    "courage":   ["brave","courage","hero","valiant","fearless"],
}


@dataclass
class Chunk:
    chunk_id:       str
    text:           str
    book:           Book
    section_number: int
    section_name:   str
    verse_start:    int | None
    verse_end:      int | None
    characters:     list[str]
    topics:         list[str]
    token_count:    int
    source_citation:str

    @classmethod
    def make_id(cls, book: Book, section: int, verse_start: int | None, text: str) -> str:
        key = f"{book.value}|{section}|{verse_start}|{text[:80]}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Serialise for Qdrant + Groq embedding pipeline."""
        return {
            "chunk_id":       self.chunk_id,
            "text":           self.text,
            "book":           self.book.value,
            "section_number": self.section_number,
            "section_name":   self.section_name,
            "verse_start":    self.verse_start,
            "verse_end":      self.verse_end,
            "characters":     self.characters,
            "topics":         self.topics,
            "token_count":    self.token_count,
            "source_citation":self.source_citation,
        }


class ShlokaChunker:
    """
    Splits book text into verse-aware chunks with overlap.
    Works for all three books regardless of text format.
    """

    def __init__(self, target_tokens: int = 400, overlap_verses: int = 2):
        self.target_tokens  = target_tokens
        self.overlap_verses = overlap_verses

    def chunk_book(
        self,
        text: str,
        book: Book,
        section_number: int,
        section_name: str,
    ) -> list[Chunk]:
        verses = self._split_verses(text)
        if not verses:
            return []

        chunks: list[Chunk] = []
        current: list[tuple[int, str]] = []
        current_tokens = 0

        for verse_num, verse_text in verses:
            vtokens = self._tokens(verse_text)
            if current_tokens + vtokens > self.target_tokens and current:
                chunk = self._build_chunk(current, book, section_number, section_name)
                if chunk.token_count >= 30:
                    chunks.append(chunk)
                current = current[-self.overlap_verses:]
                current_tokens = sum(self._tokens(v) for _, v in current)

            current.append((verse_num, verse_text))
            current_tokens += vtokens

        if current:
            chunk = self._build_chunk(current, book, section_number, section_name)
            if chunk.token_count >= 30:
                chunks.append(chunk)

        return chunks

    # ── Private ──────────────────────────────────────────────────

    def _split_verses(self, text: str) -> list[tuple[int, str]]:
        """Split text into (verse_number, verse_text) pairs."""
        # Pattern: lines starting with a number followed by period/dot
        parts = re.split(r"\n(?=\s*\d+[.)]\s)", text)
        if len(parts) > 3:
            result = []
            for i, block in enumerate(parts):
                block = block.strip()
                if not block:
                    continue
                m = re.match(r"^(\d+)[.)]\s*", block)
                vnum = int(m.group(1)) if m else i + 1
                vtext = re.sub(r"^\d+[.)]\s*", "", block).strip()
                if vtext:
                    result.append((vnum, vtext))
            return result

        # Fallback: split by double newlines (paragraphs)
        paras = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) > 20]
        return list(enumerate(paras, start=1))

    def _build_chunk(
        self,
        verses: list[tuple[int, str]],
        book: Book,
        section_number: int,
        section_name: str,
    ) -> Chunk:
        vnums = [vn for vn, _ in verses if vn]
        verse_start = min(vnums) if vnums else None
        verse_end   = max(vnums) if vnums else None

        # ── Embed verse labels inline so the Guru sees them in context ──
        # Each verse rendered as:  [Shloka 12]  text...
        # or for Gita:             [BG 2.12]    text...
        labeled_lines = []
        for vn, vt in verses:
            label = self._verse_label(book, section_number, vn)
            labeled_lines.append(f"[{label}] {vt}")
        text = "\n".join(labeled_lines)

        chars  = self._find_characters(text, book)
        topics = self._find_topics(text)
        tokens = self._tokens(text)
        citation = self._citation(book, section_number, section_name, verse_start, verse_end)
        cid = Chunk.make_id(book, section_number, verse_start, text)

        return Chunk(
            chunk_id=cid, text=text, book=book,
            section_number=section_number, section_name=section_name,
            verse_start=verse_start, verse_end=verse_end,
            characters=chars, topics=topics,
            token_count=tokens, source_citation=citation,
        )

    @staticmethod
    def _verse_label(book: Book, section_number: int, verse_number: int | None) -> str:
        """
        Build a concise inline label for a verse so the Guru can cite it naturally.

        Bhagavad Gita → BG 2.47    (chapter.verse)
        Mahabharata   → MB Adi Parva, Shloka 12
        Ramayana      → RY Sundara Kanda, Shloka 5
        """
        if verse_number is None:
            verse_number = 1
        if book == Book.BHAGAVAD_GITA:
            return f"BG {section_number}.{verse_number}"
        sec_name = SECTION_NAMES[book].get(section_number, f"Section {section_number}")
        prefix = "MB" if book == Book.MAHABHARATA else "RY"
        return f"{prefix} {sec_name}, Shloka {verse_number}"

    @staticmethod
    def _find_characters(text: str, book: Book) -> list[str]:
        lower = text.lower()
        return [c for c in CHARACTERS.get(book, []) if c.lower() in lower]

    @staticmethod
    def _find_topics(text: str) -> list[str]:
        lower = text.lower()
        return [t for t, kws in TOPIC_KEYWORDS.items() if any(k in lower for k in kws)]

    @staticmethod
    def _tokens(text: str) -> int:
        return max(1, len(text) // 4)

    @staticmethod
    def _citation(
        book: Book, sec_num: int, sec_name: str,
        vs: int | None, ve: int | None,
    ) -> str:
        book_label = {
            Book.MAHABHARATA:  "Mahabharata",
            Book.RAMAYANA:     "Ramayana",
            Book.BHAGAVAD_GITA:"Bhagavad Gita",
        }[book]
        sec_label = {
            Book.MAHABHARATA:  "Parva",
            Book.RAMAYANA:     "Kanda",
            Book.BHAGAVAD_GITA:"Chapter",
        }[book]
        verse_str = ""
        if vs is not None:
            verse_str = f", Verses {vs}–{ve}" if ve and ve != vs else f", Verse {vs}"
        return f"{book_label} — {sec_name} ({sec_label} {sec_num}){verse_str}"


def get_section_map(book: Book) -> dict[int, str]:
    return SECTION_NAMES[book]
"""
ingestion/chunker.py — Chapter-aware shloka chunker with precise citations.

Every chunk knows EXACTLY where it comes from:
  BG.2.47   → Bhagavad Gita, Chapter 2, Verse 47
  MB.6.17   → Mahabharata, Bhishma Parva (Parva 6), Verse 17
  RY.5.3    → Ramayana, Sundara Kanda (Kanda 5), Verse 3

File naming convention (produced by prepare_data.py):
  bhagavad_gita/chapter_02_sankhya_yoga.txt
  mahabharata/06_bhishma_parva.txt
  ramayana/05_sundara_kanda.txt
"""
from __future__ import annotations
import hashlib, re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Book(str, Enum):
    MAHABHARATA   = "mahabharata"
    RAMAYANA      = "ramayana"
    BHAGAVAD_GITA = "bhagavad_gita"


# ── Section name registries ────────────────────────────────────────

PARVA_NAMES = {
    1:"Adi Parva", 2:"Sabha Parva", 3:"Vana Parva", 4:"Virata Parva",
    5:"Udyoga Parva", 6:"Bhishma Parva", 7:"Drona Parva", 8:"Karna Parva",
    9:"Shalya Parva", 10:"Sauptika Parva", 11:"Stri Parva", 12:"Shanti Parva",
    13:"Anushasana Parva", 14:"Ashvamedhika Parva", 15:"Ashramavasika Parva",
    16:"Mausala Parva", 17:"Mahaprasthanika Parva", 18:"Svargarohana Parva",
}
KANDA_NAMES = {
    1:"Bala Kanda", 2:"Ayodhya Kanda", 3:"Aranya Kanda",
    4:"Kishkindha Kanda", 5:"Sundara Kanda", 6:"Yuddha Kanda", 7:"Uttara Kanda",
}
CHAPTER_NAMES = {
    1:"Arjuna Visada Yoga", 2:"Sankhya Yoga", 3:"Karma Yoga",
    4:"Jnana Karma Sanyasa Yoga", 5:"Karma Sanyasa Yoga", 6:"Dhyana Yoga",
    7:"Jnana Vijnana Yoga", 8:"Aksara Brahma Yoga", 9:"Raja Vidya Guhya Yoga",
    10:"Vibhuti Yoga", 11:"Vishwarupa Darshana Yoga", 12:"Bhakti Yoga",
    13:"Kshetra Kshetrajna Yoga", 14:"Gunatraya Vibhaga Yoga",
    15:"Purushottama Yoga", 16:"Daivasura Sampad Yoga",
    17:"Shraddhatraya Yoga", 18:"Moksha Sanyasa Yoga",
}

def get_section_map(book: Book) -> dict[int, str]:
    if book == Book.MAHABHARATA:   return PARVA_NAMES
    if book == Book.RAMAYANA:      return KANDA_NAMES
    if book == Book.BHAGAVAD_GITA: return CHAPTER_NAMES
    return {}


# ── Characters & Topics ────────────────────────────────────────────

CHARACTERS = {
    Book.MAHABHARATA: [
        "Arjuna","Krishna","Yudhishthira","Bhima","Nakula","Sahadeva",
        "Draupadi","Duryodhana","Bhishma","Drona","Karna","Kunti","Gandhari",
        "Dhritarashtra","Pandu","Ashwatthama","Vyasa","Shakuni","Vidura",
        "Abhimanyu","Ghatotkacha","Sanjaya","Subhadra","Hidimba",
    ],
    Book.RAMAYANA: [
        "Rama","Sita","Lakshmana","Hanuman","Ravana","Bharata","Shatrughna",
        "Dasharatha","Kaikeyi","Kaushalya","Sumitra","Sugriva","Vali",
        "Vibhishana","Jatayu","Mandodari","Tara","Angada","Nala","Sampati",
        "Maricha","Surpanakha","Kumbhakarna","Indrajit","Agastya",
    ],
    Book.BHAGAVAD_GITA: [
        "Arjuna","Krishna","Dhritarashtra","Sanjaya","Bhishma","Drona",
    ],
}

TOPICS = {
    "dharma":    ["dharma","duty","righteousness","righteous","sacred duty"],
    "karma":     ["karma","action","deed","fruit","result","work"],
    "war":       ["battle","war","warrior","army","weapon","bow","arrow","fight","combat"],
    "devotion":  ["devotion","bhakti","worship","prayer","divine","god","lord","surrender"],
    "wisdom":    ["wisdom","knowledge","truth","teach","lesson","philosophy","enlighten"],
    "exile":     ["exile","forest","banishment","wander","fourteen years","twelve years"],
    "moksha":    ["liberation","moksha","salvation","soul","atman","brahman","eternal"],
    "sacrifice": ["sacrifice","yagna","offering","ritual","fire","oblation"],
    "courage":   ["brave","courage","hero","valiant","fearless","warrior"],
    "love":      ["love","marriage","wife","husband","devotion","beloved","faithful"],
}


# ── Verse label patterns ───────────────────────────────────────────
# Our prepare_data.py inserts labels like [BG.2.47] [MB.6.17] [RY.5.3]
VERSE_LABEL_RE = re.compile(r"^\[([A-Z]+)\.(\d+)\.(\d+)\]\s*(.+)", re.MULTILINE)


@dataclass
class Chunk:
    chunk_id:       str
    text:           str          # labeled text shown to Guru
    clean_text:     str          # text without labels (for embeddings)
    book:           Book
    section_number: int
    section_name:   str
    verse_start:    int | None
    verse_end:      int | None
    characters:     list[str]
    topics:         list[str]
    token_count:    int
    source_citation:str          # e.g. "Bhagavad Gita — Chapter 2 (Sankhya Yoga), Verses 11-20"
    inline_ref:     str          # e.g. "BG.2.11-20" for compact in-conversation use

    @classmethod
    def make_id(cls, book: Book, sec: int, vs: int | None, text: str) -> str:
        key = f"{book.value}|{sec}|{vs}|{text[:60]}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "chunk_id":       self.chunk_id,
            "text":           self.text,
            "clean_text":     self.clean_text,
            "book":           self.book.value,
            "section_number": self.section_number,
            "section_name":   self.section_name,
            "verse_start":    self.verse_start,
            "verse_end":      self.verse_end,
            "characters":     self.characters,
            "topics":         self.topics,
            "token_count":    self.token_count,
            "source_citation":self.source_citation,
            "inline_ref":     self.inline_ref,
        }


class ShlokaChunker:
    """
    Chunks book text into verse-groups with precise citations.

    Understands labeled verses ([BG.2.47], [MB.6.17], [RY.5.3])
    produced by prepare_data.py, and falls back to numbered-line
    detection for plain text files.
    """

    def __init__(self, target_tokens: int = 350, overlap_verses: int = 2):
        self.target_tokens  = target_tokens
        self.overlap_verses = overlap_verses

    def chunk_file(self, file_path: Path, book: Book, section_number: int, section_name: str) -> list[Chunk]:
        """Chunk a single book section file."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return self.chunk_book(text, book, section_number, section_name)

    def chunk_book(self, text: str, book: Book, section_number: int, section_name: str) -> list[Chunk]:
        """Split text into overlapping verse-group chunks."""
        verses = self._extract_verses(text, book, section_number)
        if not verses:
            return []

        chunks: list[Chunk] = []
        i = 0
        while i < len(verses):
            group: list[tuple[int, str]] = []
            tokens = 0
            j = i
            while j < len(verses) and tokens < self.target_tokens:
                vnum, vtext = verses[j]
                group.append((vnum, vtext))
                tokens += max(1, len(vtext) // 4)
                j += 1

            if group:
                chunk = self._build_chunk(group, book, section_number, section_name)
                if chunk.token_count >= 20:
                    chunks.append(chunk)

            # Advance with overlap
            step = max(1, len(group) - self.overlap_verses)
            i += step

        return chunks

    # ── Private ──────────────────────────────────────────────────

    def _extract_verses(
        self, text: str, book: Book, section_number: int
    ) -> list[tuple[int, str]]:
        """
        Extract (verse_number, verse_text) pairs.
        Handles both labeled [BG.2.47] format and plain numbered "47. text" format.
        """
        verses: list[tuple[int, str]] = []

        # Strategy 1: labeled verses from prepare_data.py
        labeled_matches = VERSE_LABEL_RE.findall(text)
        if labeled_matches:
            for _book_code, _sec, vnum_str, vtext in labeled_matches:
                vnum  = int(vnum_str)
                vtext = vtext.strip()
                if vtext:
                    verses.append((vnum, vtext))
            if verses:
                return verses

        # Strategy 2: plain "N. text" numbered lines
        plain = re.findall(r"^(\d+)\.\s+(.+?)$", text, re.MULTILINE)
        if len(plain) >= 3:
            for vnum_str, vtext in plain:
                vtext = vtext.strip()
                if vtext and len(vtext) > 15:
                    verses.append((int(vnum_str), vtext))
            if verses:
                return verses

        # Strategy 3: paragraph-based fallback (non-empty paragraphs)
        paras = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) > 30]
        # Skip header lines
        paras = [p for p in paras if not re.match(r"^(BHAGAVAD|MAHABHARATA|RAMAYANA|===)", p)]
        return [(i + 1, p) for i, p in enumerate(paras)]

    def _build_chunk(
        self,
        verses: list[tuple[int, str]],
        book: Book,
        section_number: int,
        section_name: str,
    ) -> Chunk:
        vnums = [vn for vn, _ in verses]
        verse_start = min(vnums) if vnums else None
        verse_end   = max(vnums) if vnums else None

        # Build labeled text (shown to Guru)
        book_code = {"mahabharata": "MB", "ramayana": "RY", "bhagavad_gita": "BG"}[book.value]
        labeled_lines = []
        for vn, vt in verses:
            labeled_lines.append(f"[{book_code}.{section_number}.{vn}] {vt}")
        labeled_text = "\n".join(labeled_lines)

        # Clean text (for embeddings — no labels)
        clean_text = "\n".join(vt for _, vt in verses)

        characters  = self._find_characters(clean_text, book)
        topics      = self._find_topics(clean_text)
        token_count = max(1, len(clean_text) // 4)
        citation    = self._build_citation(book, section_number, section_name, verse_start, verse_end)
        inline_ref  = self._build_inline_ref(book_code, section_number, verse_start, verse_end)
        chunk_id    = Chunk.make_id(book, section_number, verse_start, clean_text)

        return Chunk(
            chunk_id=chunk_id,
            text=labeled_text,
            clean_text=clean_text,
            book=book,
            section_number=section_number,
            section_name=section_name,
            verse_start=verse_start,
            verse_end=verse_end,
            characters=characters,
            topics=topics,
            token_count=token_count,
            source_citation=citation,
            inline_ref=inline_ref,
        )

    @staticmethod
    def _find_characters(text: str, book: Book) -> list[str]:
        lower = text.lower()
        return [c for c in CHARACTERS.get(book, []) if c.lower() in lower]

    @staticmethod
    def _find_topics(text: str) -> list[str]:
        lower = text.lower()
        return [t for t, kws in TOPICS.items() if any(k in lower for k in kws)]

    @staticmethod
    def _build_citation(
        book: Book, sec_num: int, sec_name: str,
        vs: int | None, ve: int | None,
    ) -> str:
        label = {
            Book.BHAGAVAD_GITA: "Bhagavad Gita",
            Book.MAHABHARATA:   "Mahabharata",
            Book.RAMAYANA:      "Ramayana",
        }[book]
        unit = {
            Book.BHAGAVAD_GITA: "Chapter",
            Book.MAHABHARATA:   "Parva",
            Book.RAMAYANA:      "Kanda",
        }[book]
        verse_str = ""
        if vs is not None:
            verse_str = f", Shloka {vs}" if vs == ve else f", Shlokas {vs}–{ve}"
        return f"{label} — {sec_name} ({unit} {sec_num}){verse_str}"

    @staticmethod
    def _build_inline_ref(book_code: str, sec_num: int, vs: int | None, ve: int | None) -> str:
        if vs is None:
            return f"{book_code}.{sec_num}"
        if vs == ve:
            return f"{book_code}.{sec_num}.{vs}"
        return f"{book_code}.{sec_num}.{vs}-{ve}"
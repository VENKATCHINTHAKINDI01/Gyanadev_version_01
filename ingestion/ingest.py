"""
ingestion/ingest.py — Ingest book files into Qdrant with precise citations.

Usage:
    python -m ingestion.ingest --all
    python -m ingestion.ingest --book mahabharata
    python -m ingestion.ingest --stats
"""
from __future__ import annotations
import argparse, logging, re, sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DATA = Path("data/sources")

BOOK_DIRS = {
    "mahabharata":   DATA / "mahabharata",
    "ramayana":      DATA / "ramayana",
    "bhagavad_gita": DATA / "bhagavad_gita",
}

# Regex to extract section number from filename
SECTION_NUM_RE = re.compile(r"^(\d+)")


def _section_num_from_file(path: Path, book: str) -> tuple[int, str]:
    """Extract (section_number, section_name) from filename."""
    from ingestion.chunker import get_section_map, Book
    bk = Book(book)
    sec_map = get_section_map(bk)

    m = SECTION_NUM_RE.match(path.stem)
    if m:
        n = int(m.group(1))
        name = sec_map.get(n, path.stem.replace("_", " ").title())
        return n, name

    # Bhagavad Gita: "chapter_02_sankhya_yoga.txt"
    m2 = re.search(r"chapter[_\s]*(\d+)", path.stem, re.IGNORECASE)
    if m2:
        n = int(m2.group(1))
        return n, sec_map.get(n, f"Chapter {n}")

    return 1, path.stem.replace("_", " ").title()


def ingest_book(book: str, pipeline, chunker) -> int:
    from ingestion.chunker import Book
    bk  = Book(book)
    dir_= BOOK_DIRS[book]

    if not dir_.exists():
        log.warning(f"  {dir_} not found — run: python scripts/prepare_data.py --{book}")
        return 0

    txt_files = sorted(dir_.glob("*.txt"))
    if not txt_files:
        log.warning(f"  No .txt files in {dir_}")
        return 0

    total = 0
    for f in txt_files:
        if f.stat().st_size < 500:
            log.warning(f"  Skipping empty file: {f.name}")
            continue
        sec_num, sec_name = _section_num_from_file(f, book)
        log.info(f"  {f.name}  →  {sec_name} (sec {sec_num})")
        chunks = chunker.chunk_file(f, bk, sec_num, sec_name)
        log.info(f"    {len(chunks)} chunks")
        if chunks:
            n = pipeline.upsert_chunks(chunks)
            total += n
    return total


def main():
    parser = argparse.ArgumentParser(description="GyanaDev book ingestion")
    parser.add_argument("--all",   action="store_true")
    parser.add_argument("--book",  choices=["mahabharata","ramayana","bhagavad_gita"])
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    from api.config import get_settings
    from db.qdrant_store import QdrantStore
    from groq_client.client import GroqClient
    from ingestion.chunker import ShlokaChunker
    from ingestion.embedder import EmbeddingPipeline

    settings = get_settings()

    if args.stats:
        qdrant = QdrantStore(settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection)
        stats  = qdrant.get_stats()
        print(f"\n📊 Corpus Stats")
        print(f"   Collection : {stats['collection']}")
        print(f"   Chunks     : {stats['total_chunks']:,}")
        print(f"   Embed dim  : {stats['embed_dim']}\n")
        return

    groq    = GroqClient(api_key=settings.groq_api_key, llm_model=settings.groq_llm_model)
    qdrant  = QdrantStore(settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection)
    chunker = ShlokaChunker(target_tokens=350, overlap_verses=2)
    pipe    = EmbeddingPipeline(groq_client=groq, qdrant_store=qdrant)

    books = list(BOOK_DIRS.keys()) if args.all else ([args.book] if args.book else [])
    if not books:
        parser.print_help(); sys.exit(1)

    total = 0
    for book in books:
        log.info(f"\n{'='*50}")
        log.info(f"📖 Ingesting: {book.upper()}")
        log.info(f"{'='*50}")
        n = ingest_book(book, pipe, chunker)
        log.info(f"  ✓ {book}: {n} new chunks stored")
        total += n

    stats = qdrant.get_stats()
    log.info(f"\n🎉 Done — corpus now has {stats['total_chunks']:,} chunks total")


if __name__ == "__main__":
    main()
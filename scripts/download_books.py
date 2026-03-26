"""
scripts/download_books.py — Download real public domain translations.

Sources (all pre-1928, fully public domain):
  Bhagavad Gita  → Edwin Arnold translation (1885) — Project Gutenberg
  Mahabharata    → Kisari Mohan Ganguli (1883-1896) — Sacred Texts
  Ramayana       → Ralph T.H. Griffith (1870-1874) — Sacred Texts

Usage:
    python scripts/download_books.py --all
    python scripts/download_books.py --gita
    python scripts/download_books.py --mahabharata
    python scripts/download_books.py --ramayana
"""
from __future__ import annotations
import argparse
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

SOURCES_DIR = Path("data/sources")
HEADERS = {
    "User-Agent": "GyanaDev-Educational-Bot/1.0 (Hindu Epics RAG for children)"
}

# ── URL maps ───────────────────────────────────────────────────────

GITA_URL = "https://www.gutenberg.org/cache/epub/2388/pg2388.txt"

# Ganguli Mahabharata on Project Gutenberg
MAHABHARATA_GUTENBERG = {
    1:  ("Adi Parva",             "https://www.gutenberg.org/cache/epub/15473/pg15473.txt"),
    2:  ("Sabha Parva",           "https://www.gutenberg.org/cache/epub/15474/pg15474.txt"),
    3:  ("Vana Parva",            "https://www.gutenberg.org/cache/epub/15476/pg15476.txt"),
    4:  ("Virata Parva",          "https://www.gutenberg.org/cache/epub/15477/pg15477.txt"),
    5:  ("Udyoga Parva",          "https://www.gutenberg.org/cache/epub/15478/pg15478.txt"),
    6:  ("Bhishma Parva",         "https://www.gutenberg.org/cache/epub/15479/pg15479.txt"),
    7:  ("Drona Parva",           "https://www.gutenberg.org/cache/epub/15480/pg15480.txt"),
    8:  ("Karna Parva",           "https://www.gutenberg.org/cache/epub/15481/pg15481.txt"),
    9:  ("Shalya Parva",          "https://www.gutenberg.org/cache/epub/15482/pg15482.txt"),
    10: ("Sauptika Parva",        "https://www.gutenberg.org/cache/epub/15483/pg15483.txt"),
    11: ("Stri Parva",            "https://www.gutenberg.org/cache/epub/15484/pg15484.txt"),
    12: ("Shanti Parva",          "https://www.gutenberg.org/cache/epub/15485/pg15485.txt"),
    13: ("Anushasana Parva",      "https://www.gutenberg.org/cache/epub/15486/pg15486.txt"),
    14: ("Ashvamedhika Parva",    "https://www.gutenberg.org/cache/epub/15487/pg15487.txt"),
    15: ("Ashramavasika Parva",   "https://www.gutenberg.org/cache/epub/15488/pg15488.txt"),
    16: ("Mausala Parva",         "https://www.gutenberg.org/cache/epub/15489/pg15489.txt"),
    17: ("Mahaprasthanika Parva", "https://www.gutenberg.org/cache/epub/15490/pg15490.txt"),
    18: ("Svargarohana Parva",    "https://www.gutenberg.org/cache/epub/15491/pg15491.txt"),
}

# Griffith Ramayana on Project Gutenberg (7 books = 7 separate ebooks)
RAMAYANA_GUTENBERG = {
    1: ("Bala Kanda",       "https://www.gutenberg.org/cache/epub/24869/pg24869.txt"),
    2: ("Ayodhya Kanda",    "https://www.gutenberg.org/cache/epub/24873/pg24873.txt"),
    3: ("Aranya Kanda",     "https://www.gutenberg.org/cache/epub/24877/pg24877.txt"),
    4: ("Kishkindha Kanda", "https://www.gutenberg.org/cache/epub/24881/pg24881.txt"),
    5: ("Sundara Kanda",    "https://www.gutenberg.org/cache/epub/24885/pg24885.txt"),
    6: ("Yuddha Kanda",     "https://www.gutenberg.org/cache/epub/24889/pg24889.txt"),
    7: ("Uttara Kanda",     "https://www.gutenberg.org/cache/epub/24893/pg24893.txt"),
}


# ── Fetchers ───────────────────────────────────────────────────────

def fetch(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt < retries - 1:
                print(f"    Retry {attempt+1}: {e}")
                time.sleep(2)
            else:
                print(f"    Failed after {retries} attempts: {e}")
    return None


def clean_gutenberg(raw: str) -> str:
    """Strip Project Gutenberg header/footer and HTML, leaving plain text."""
    # Remove Gutenberg header
    start_markers = ["*** START OF", "***START OF", "THE SONG CELESTIAL", "BHAGAVAD-GITA"]
    end_markers   = ["*** END OF", "***END OF", "End of Project Gutenberg"]

    lines = raw.splitlines()
    start_idx, end_idx = 0, len(lines)

    for i, line in enumerate(lines):
        if any(m in line.upper() for m in start_markers) and i < 200:
            start_idx = i + 1
            break
    for i in range(len(lines)-1, 0, -1):
        if any(m in lines[i].upper() for m in end_markers):
            end_idx = i
            break

    text = "\n".join(lines[start_idx:end_idx])
    # Normalize whitespace
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def clean_sacred_texts_html(html: str) -> str:
    """Extract readable text from Sacred Texts HTML pages."""
    # Remove script/style/head
    html = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", "", html, flags=re.DOTALL|re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
        "&mdash;": "—", "&ndash;": "–", "&lsquo;": "'",
        "&rsquo;": "'", "&ldquo;": '"', "&rdquo;": '"',
    }
    for ent, char in replacements.items():
        text = text.replace(ent, char)
    # Clean whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def get_sacred_texts_section_links(index_url: str) -> list[str]:
    """Get all chapter/section links from a Sacred Texts index page."""
    html = fetch(index_url)
    if not html:
        return []
    base = index_url.rsplit("/", 1)[0] + "/"
    links = re.findall(r'href=["\']([^"\']+\.htm)["\']', html, re.IGNORECASE)
    # Filter to section files (not the index itself)
    section_links = []
    seen = set()
    for link in links:
        if link.startswith("http"):
            full = link
        else:
            full = base + link.lstrip("./")
        # Only include links to same directory section files
        if "index" not in full.lower() and full not in seen:
            section_links.append(full)
            seen.add(full)
    return section_links[:100]  # cap at 100 sections per book


# ── Downloaders ────────────────────────────────────────────────────

def download_gita():
    """Download Edwin Arnold's 'The Song Celestial' (Bhagavad Gita) from Gutenberg."""
    print("\n📖 Downloading Bhagavad Gita (Edwin Arnold, 1885)...")
    out_dir = SOURCES_DIR / "bhagavad_gita"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = fetch(GITA_URL)
    if not raw:
        print("  ✗ Failed to download from Project Gutenberg")
        print("  Manual download: https://www.gutenberg.org/ebooks/2388")
        return False

    text = clean_gutenberg(raw)
    out_path = out_dir / "gita.txt"
    out_path.write_text(text, encoding="utf-8")
    size_kb = out_path.stat().st_size // 1024
    print(f"  ✓ Saved: {out_path} ({size_kb} KB, {len(text.splitlines())} lines)")
    return True


def download_mahabharata():
    """Download Ganguli Mahabharata from Project Gutenberg (18 parvas)."""
    print("\n📖 Downloading Mahabharata (Ganguli, 1883-1896) from Project Gutenberg...")
    out_dir = SOURCES_DIR / "mahabharata"
    out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for parva_num, (parva_name, url) in MAHABHARATA_GUTENBERG.items():
        fname = f"{parva_num:02d}_{parva_name.lower().replace(' ', '_')}.txt"
        out_path = out_dir / fname

        if out_path.exists() and out_path.stat().st_size > 5000:
            print(f"  ✓ {parva_name} already exists — skipping")
            saved += 1
            continue

        print(f"  Downloading {parva_name}...", end=" ", flush=True)
        raw = fetch(url)
        if not raw:
            print("✗ Failed")
            continue

        text = clean_gutenberg(raw)
        if len(text) < 1000:
            print(f"✗ Too short ({len(text)} chars)")
            continue

        header = f"=== {parva_name} (Parva {parva_num}) ===\n\n"
        out_path.write_text(header + text, encoding="utf-8")
        size_kb = out_path.stat().st_size // 1024
        print(f"✓ {size_kb} KB, {len(text.splitlines()):,} lines")
        saved += 1
        time.sleep(1)

    print(f"  Saved {saved}/{len(MAHABHARATA_GUTENBERG)} parvas")
    return saved > 0


def download_ramayana():
    """Download Griffith Ramayana from Project Gutenberg (7 books)."""
    print("\n📖 Downloading Ramayana (Griffith, 1870-1874) from Project Gutenberg...")
    out_dir = SOURCES_DIR / "ramayana"
    out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for kanda_num, (kanda_name, url) in RAMAYANA_GUTENBERG.items():
        fname = f"{kanda_num:02d}_{kanda_name.lower().replace(' ', '_')}.txt"
        out_path = out_dir / fname

        if out_path.exists() and out_path.stat().st_size > 5000:
            print(f"  ✓ {kanda_name} already exists — skipping")
            saved += 1
            continue

        print(f"  Downloading {kanda_name}...", end=" ", flush=True)
        raw = fetch(url)
        if not raw:
            print(f"✗ Failed")
            continue

        text = clean_gutenberg(raw)
        if len(text) < 1000:
            print(f"✗ Too short ({len(text)} chars) — may be wrong file")
            continue

        header = f"=== {kanda_name} (Kanda {kanda_num}) ===\n\n"
        out_path.write_text(header + text, encoding="utf-8")
        size_kb = out_path.stat().st_size // 1024
        print(f"✓ {size_kb} KB, {len(text.splitlines()):,} lines")
        saved += 1
        time.sleep(1)

    print(f"  Saved {saved}/{len(RAMAYANA_GUTENBERG)} kandas")
    return saved > 0


def show_stats():
    """Show what's currently in the data folder."""
    print("\n📊 Current data/sources contents:")
    total_size = 0
    for book_dir in sorted(SOURCES_DIR.iterdir()):
        if not book_dir.is_dir():
            continue
        files = sorted(book_dir.glob("*.txt"))
        if not files:
            print(f"  {book_dir.name}/ — empty")
            continue
        book_size = sum(f.stat().st_size for f in files)
        total_size += book_size
        print(f"  {book_dir.name}/ — {len(files)} files, {book_size//1024} KB total")
        for f in files:
            lines = f.read_text(encoding="utf-8", errors="replace").count("\n")
            print(f"    {f.name}: {f.stat().st_size//1024} KB, {lines:,} lines")
    print(f"\n  Total: {total_size//1024} KB")


def main():
    parser = argparse.ArgumentParser(
        description="Download public domain Hindu epics for GyanaDev"
    )
    parser.add_argument("--all",         action="store_true", help="Download all three books")
    parser.add_argument("--gita",        action="store_true", help="Download Bhagavad Gita only")
    parser.add_argument("--mahabharata", action="store_true", help="Download Mahabharata only")
    parser.add_argument("--ramayana",    action="store_true", help="Download Ramayana only")
    parser.add_argument("--stats",       action="store_true", help="Show current data stats")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if not any([args.all, args.gita, args.mahabharata, args.ramayana]):
        parser.print_help()
        print("\nExample: python scripts/download_books.py --all")
        return

    print("╔══════════════════════════════════════════════════════╗")
    print("║  GyanaDev — Public Domain Book Downloader           ║")
    print("║  Sources: Project Gutenberg + Sacred Texts          ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\nAll texts are pre-1928 public domain translations.")
    print("Downloading with respectful delays between requests.\n")

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    if args.all or args.gita:
        results["gita"] = download_gita()
    if args.all or args.mahabharata:
        results["mahabharata"] = download_mahabharata()
    if args.all or args.ramayana:
        results["ramayana"] = download_ramayana()

    print("\n══════════════════════════════════════════════════════")
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")

    show_stats()

    print("\n  Next step: python -m ingestion.ingest --all")
    print("  This will chunk and embed all downloaded texts into Qdrant.\n")


if __name__ == "__main__":
    main()
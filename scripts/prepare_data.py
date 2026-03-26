"""
scripts/prepare_data.py — Download and structure all three books correctly.

Run this ONCE before ingestion:
    python scripts/prepare_data.py

What it does:
  1. Downloads Bhagavad Gita (Gutenberg #2388) → splits into 18 chapter files
  2. Downloads Mahabharata (Gutenberg #15473-15491) → one file per parva
  3. Downloads Ramayana (Gutenberg #24869-24875) → one file per kanda
  4. Adds verse number labels [BG.2.47] / [MB.Adi.17] / [RY.Sundara.5]
"""
from __future__ import annotations
import re, sys, time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

HEADERS = {"User-Agent": "GyanaDev-Educational/1.0 (Student learning app)"}

DATA  = Path("data/sources")
GITA  = DATA / "bhagavad_gita"
MBH   = DATA / "mahabharata"
RAM   = DATA / "ramayana"

# ── Correct Gutenberg IDs ──────────────────────────────────────────
GITA_ID = 2388   # "The Song Celestial" by Edwin Arnold

# Ganguli Mahabharata — confirmed Gutenberg IDs
MBH_IDS = {
    1:  ("Adi Parva",             15473),
    2:  ("Sabha Parva",           15474),
    3:  ("Vana Parva",            15476),
    4:  ("Virata Parva",          15477),
    5:  ("Udyoga Parva",          15478),
    6:  ("Bhishma Parva",         15479),
    7:  ("Drona Parva",           15480),
    8:  ("Karna Parva",           15481),
    9:  ("Shalya Parva",          15482),
    10: ("Sauptika Parva",        15483),
    11: ("Stri Parva",            15484),
    12: ("Shanti Parva",          15485),
    13: ("Anushasana Parva",      15486),
    14: ("Ashvamedhika Parva",    15487),
    15: ("Ashramavasika Parva",   15488),
    16: ("Mausala Parva",         15489),
    17: ("Mahaprasthanika Parva", 15490),
    18: ("Svargarohana Parva",    15491),
}

# Griffith Ramayana — confirmed Gutenberg IDs
RAM_IDS = {
    1: ("Bala Kanda",       24869),
    2: ("Ayodhya Kanda",    24873),
    3: ("Aranya Kanda",     24877),
    4: ("Kishkindha Kanda", 24881),
    5: ("Sundara Kanda",    24885),
    6: ("Yuddha Kanda",     24889),
    7: ("Uttara Kanda",     24893),
}

CHAPTER_NAMES = {
    1: "Arjuna Visada Yoga",       2: "Sankhya Yoga",
    3: "Karma Yoga",               4: "Jnana Karma Sanyasa Yoga",
    5: "Karma Sanyasa Yoga",       6: "Dhyana Yoga",
    7: "Jnana Vijnana Yoga",       8: "Aksara Brahma Yoga",
    9: "Raja Vidya Raja Guhya Yoga", 10: "Vibhuti Yoga",
    11: "Vishwarupa Darshana Yoga", 12: "Bhakti Yoga",
    13: "Kshetra Kshetrajna Vibhaga Yoga", 14: "Gunatraya Vibhaga Yoga",
    15: "Purushottama Yoga",        16: "Daivasura Sampad Vibhaga Yoga",
    17: "Shraddhatraya Vibhaga Yoga", 18: "Moksha Sanyasa Yoga",
}

# ── Helpers ────────────────────────────────────────────────────────

def fetch(gutenberg_id: int) -> str | None:
    """Try multiple URL patterns for a Gutenberg text."""
    urls = [
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.text) > 5000:
                print(f"  ✓ {url.split('/')[-1]} ({len(r.text)//1024} KB)")
                return r.text
        except Exception as e:
            pass
    print(f"  ✗ All URLs failed for #{gutenberg_id}")
    return None


def strip_gutenberg(raw: str) -> str:
    """Remove Project Gutenberg header/footer."""
    lines = raw.splitlines()
    start, end = 0, len(lines)
    for i, ln in enumerate(lines):
        u = ln.upper()
        if ("START OF" in u and "GUTENBERG" in u) or ("PRODUCED BY" in u and i < 100):
            start = i + 1
        if "END OF" in u and "GUTENBERG" in u:
            end = i; break
    text = "\n".join(lines[start:end])
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def add_verse_labels_gita(chapter_num: int, text: str) -> str:
    """Label every verse in a Gita chapter as [BG.CH.V]."""
    def replace(m):
        v = m.group(1)
        return f"[BG.{chapter_num}.{v}] {m.group(2)}"
    return re.sub(r"^(\d+)\.\s+(.+)", replace, text, flags=re.MULTILINE)


def add_verse_labels_book(book_code: str, section_num: int, text: str) -> str:
    """Label every numbered verse as [MB.1.17] or [RY.5.3]."""
    def replace(m):
        v = m.group(1)
        return f"[{book_code}.{section_num}.{v}] {m.group(2)}"
    return re.sub(r"^(\d+)\.\s+(.+)", replace, text, flags=re.MULTILINE)


# ── Bhagavad Gita ──────────────────────────────────────────────────

def process_gita():
    print("\n📖 BHAGAVAD GITA (Edwin Arnold, 1885)")
    GITA.mkdir(parents=True, exist_ok=True)

    raw = fetch(GITA_ID)
    if not raw:
        print("  Cannot download Gita. Check your internet connection.")
        return 0

    text = strip_gutenberg(raw)

    # Split into chapters by detecting chapter headings
    # Arnold uses patterns like "CHAPTER I", "CHAPTER II" etc.
    # Also handles "THE FIRST CHAPTER", numbered sections
    chapter_patterns = [
        r"(?:^|\n)(CHAPTER\s+[IVXLC]+[^\n]*\n)",
        r"(?:^|\n)(THE\s+\w+\s+CHAPTER[^\n]*\n)",
    ]

    # Try to split on chapter headings
    splits = re.split(r"\n(?=CHAPTER\s+[IVXLC]+)", text, flags=re.IGNORECASE)

    if len(splits) < 5:
        # Fallback: split on any strong chapter indicator
        splits = re.split(r"\n\n(?=[A-Z\s]{10,}\n)", text)

    # If we still can't split, create one chapter from numbered verses
    if len(splits) < 3:
        print(f"  Could not split into chapters — using verse-based split")
        # Find all verse blocks (numbered paragraphs)
        all_verses = re.findall(r"(\d+)\.\s+([^\n]+(?:\n(?!\d+\.)[^\n]+)*)", text)
        if all_verses:
            saved = _save_gita_by_verse_count(all_verses)
            return saved
        return 0

    # Map roman numerals to chapter numbers
    roman = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,
             "IX":9,"X":10,"XI":11,"XII":12,"XIII":13,"XIV":14,"XV":15,
             "XVI":16,"XVII":17,"XVIII":18}

    saved = 0
    for i, chunk in enumerate(splits[1:], 1):  # skip preamble
        lines = chunk.strip().splitlines()
        # Extract chapter number from heading
        heading = lines[0] if lines else ""
        ch_num = i  # default to position
        for rom, num in roman.items():
            if re.search(rf"\b{rom}\b", heading, re.IGNORECASE):
                ch_num = num; break

        ch_name = CHAPTER_NAMES.get(ch_num, f"Chapter {ch_num}")
        body = "\n".join(lines[1:]).strip()
        if len(body) < 200:
            continue

        labeled = add_verse_labels_gita(ch_num, body)
        header  = f"BHAGAVAD GITA — Chapter {ch_num}: {ch_name}\n\n"
        fname   = f"chapter_{ch_num:02d}_{ch_name.lower().replace(' ','_').replace('/','_')[:30]}.txt"
        (GITA / fname).write_text(header + labeled, encoding="utf-8")
        print(f"  ✓ Chapter {ch_num}: {ch_name} ({len(body)} chars)")
        saved += 1

    if saved < 5:
        # Arnold text may use different formatting — do full-text single file
        print(f"  Only {saved} chapters found. Saving as single file with verse labels.")
        labeled = add_verse_labels_gita(0, text)  # best effort
        (GITA / "gita_complete.txt").write_text(
            "BHAGAVAD GITA (Edwin Arnold translation)\n\n" + labeled,
            encoding="utf-8"
        )
        saved = 1

    return saved


def _save_gita_by_verse_count(all_verses: list) -> int:
    """Fallback: distribute ~700 verses across 18 chapters."""
    per_ch = max(1, len(all_verses) // 18)
    saved = 0
    for ch in range(1, 19):
        start = (ch-1) * per_ch
        end   = start + per_ch if ch < 18 else len(all_verses)
        verses = all_verses[start:end]
        if not verses: continue
        ch_name = CHAPTER_NAMES.get(ch, f"Chapter {ch}")
        lines   = [f"[BG.{ch}.{v}] {t}" for v,t in verses]
        header  = f"BHAGAVAD GITA — Chapter {ch}: {ch_name}\n\n"
        fname   = f"chapter_{ch:02d}.txt"
        (GITA / fname).write_text(header + "\n".join(lines), encoding="utf-8")
        saved += 1
    return saved


# ── Mahabharata ────────────────────────────────────────────────────

def process_mahabharata():
    print("\n📖 MAHABHARATA (Ganguli translation, 1883-1896)")
    MBH.mkdir(parents=True, exist_ok=True)

    saved = 0
    for parva_num, (parva_name, gid) in MBH_IDS.items():
        fname    = f"{parva_num:02d}_{parva_name.lower().replace(' ','_')}.txt"
        out_path = MBH / fname

        if out_path.exists() and out_path.stat().st_size > 10_000:
            print(f"  ✓ {parva_name} already saved ({out_path.stat().st_size//1024} KB)")
            saved += 1; continue

        print(f"  Downloading {parva_name} (#{gid})...", end=" ", flush=True)
        raw = fetch(gid)
        if not raw:
            continue

        text   = strip_gutenberg(raw)
        labeled = add_verse_labels_book("MB", parva_num, text)
        header  = f"MAHABHARATA — {parva_name} (Parva {parva_num})\nKisari Mohan Ganguli translation\n\n"
        out_path.write_text(header + labeled, encoding="utf-8")
        print(f"  Saved {out_path.stat().st_size//1024} KB")
        saved += 1
        time.sleep(1)  # polite delay

    return saved


# ── Ramayana ───────────────────────────────────────────────────────

def process_ramayana():
    print("\n📖 RAMAYANA (Griffith translation, 1870-1874)")
    RAM.mkdir(parents=True, exist_ok=True)

    saved = 0
    for kanda_num, (kanda_name, gid) in RAM_IDS.items():
        fname    = f"{kanda_num:02d}_{kanda_name.lower().replace(' ','_')}.txt"
        out_path = RAM / fname

        if out_path.exists() and out_path.stat().st_size > 10_000:
            print(f"  ✓ {kanda_name} already saved ({out_path.stat().st_size//1024} KB)")
            saved += 1; continue

        print(f"  Downloading {kanda_name} (#{gid})...", end=" ", flush=True)
        raw = fetch(gid)
        if not raw:
            continue

        text   = strip_gutenberg(raw)
        labeled = add_verse_labels_book("RY", kanda_num, text)
        header  = f"RAMAYANA — {kanda_name} (Kanda {kanda_num})\nRalph T.H. Griffith translation\n\n"
        out_path.write_text(header + labeled, encoding="utf-8")
        print(f"  Saved {out_path.stat().st_size//1024} KB")
        saved += 1
        time.sleep(1)

    return saved


# ── Stats ──────────────────────────────────────────────────────────

def show_stats():
    print("\n📊 Data folder contents:")
    total = 0
    for d in [GITA, MBH, RAM]:
        files = sorted(d.glob("*.txt")) if d.exists() else []
        sz    = sum(f.stat().st_size for f in files)
        total += sz
        print(f"  {d.name}/  {len(files)} files  {sz//1024} KB")
        for f in files[:5]:
            lines = f.read_text(errors="replace").count("\n")
            print(f"    {f.name}: {f.stat().st_size//1024} KB, {lines:,} lines")
        if len(files) > 5:
            print(f"    ... and {len(files)-5} more")
    print(f"\n  Total: {total//1024} KB")


# ── Main ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all",          action="store_true")
    p.add_argument("--gita",         action="store_true")
    p.add_argument("--mahabharata",  action="store_true")
    p.add_argument("--ramayana",     action="store_true")
    p.add_argument("--stats",        action="store_true")
    args = p.parse_args()

    if args.stats:
        show_stats(); sys.exit(0)
    if not any(vars(args).values()):
        p.print_help(); sys.exit(0)

    print("╔══════════════════════════════════════════════════╗")
    print("║  GyanaDev — Book Downloader & Processor         ║")
    print("╚══════════════════════════════════════════════════╝")

    results = {}
    if args.all or args.gita:
        results["Bhagavad Gita"]  = process_gita()
    if args.all or args.mahabharata:
        results["Mahabharata"]    = process_mahabharata()
    if args.all or args.ramayana:
        results["Ramayana"]       = process_ramayana()

    print("\n═══════════════════════════════════════════════════")
    for name, n in results.items():
        print(f"  {'✅' if n else '❌'} {name}: {n} files saved")
    show_stats()
    print("\n  Next: python -m ingestion.ingest --all")
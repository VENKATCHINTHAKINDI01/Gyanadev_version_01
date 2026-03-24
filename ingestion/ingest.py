"""
ingestion/ingest.py — Book ingestion CLI.

Usage:
    python -m ingestion.ingest --samples   # create sample texts + ingest
    python -m ingestion.ingest --all       # ingest all books from data/sources/
    python -m ingestion.ingest --book mahabharata
    python -m ingestion.ingest --stats     # show corpus stats
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

from api.config import get_settings
from db.qdrant_store import QdrantStore
from groq_client.client import GroqClient
from ingestion.chunker import Book, ShlokaChunker, get_section_map
from ingestion.embedder import EmbeddingPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCES_DIR = Path("data/sources")
SOURCE_FILES = {
    Book.MAHABHARATA:   SOURCES_DIR / "mahabharata",
    Book.RAMAYANA:      SOURCES_DIR / "ramayana",
    Book.BHAGAVAD_GITA: SOURCES_DIR / "bhagavad_gita" / "gita.txt",
}

# ── Sample texts for development (public domain) ──────────────────

SAMPLE_TEXTS = {
    Book.BHAGAVAD_GITA: {
        1: ("Chapter 1", """1. Dhritarashtra said: In the field of virtue, in the field of Kuru, assembled together eager for battle, what did my sons and the sons of Pandu do, O Sanjaya?
2. Sanjaya said: Having seen the army of the Pandavas arrayed for battle, King Duryodhana approached his teacher Drona and spoke these words.
3. Behold, O Teacher, this mighty army of the sons of Pandu, arrayed by thy talented pupil, the son of Drupada.
4. Here are heroes, mighty archers, equal in battle to Bhima and Arjuna — Yuyudhana, Virata and Drupada.
5. Dhrishtaketu, Chekitana, the valiant king of Kashi, Purujit, Kuntibhoja and Shaibya, the best of men.
6. The strong Yudhamanyu and the brave Uttamauja, the son of Subhadra and the sons of Draupadi — all of them great car-warriors.
7. Know also, O best of the twice-born, the leaders of my army. For thy information I will name the commanders of my forces.
8. Thyself and Bhishma and Karna and Kripa, always victorious in battle — Ashwatthama, Vikarna and the son of Somadatta.
9. And also many other heroes who have risked their lives for my sake, armed with various weapons, all experienced in war.
10. This army of ours marshalled by Bhishma is insufficient, whereas their army marshalled by Bhima is sufficient.
11. Therefore let all of you, stationed in your respective positions in the divisions of the army, protect Bhishma alone.
12. Then the mighty Bhishma, the grandsire of the Kurus, the oldest, roared like a lion and blew his conch shell to cheer Duryodhana."""),
        2: ("Chapter 2", """1. Sanjaya said: To him who was thus overwhelmed with pity, whose eyes were full of tears and agitated, who was overwhelmed with grief, Krishna spoke these words.
2. The Supreme Personality of Godhead said: My dear Arjuna, how have these impurities come upon you? They are not at all befitting a man who knows the value of life. Do not yield to this degrading impotence.
3. O son of Pritha, do not yield to this degrading impotence. It does not become you. Give up such petty weakness of heart and arise, O chastiser of the enemy.
4. Arjuna said: O killer of enemies, O killer of Madhu, how can I counterattack with arrows in battle against men like Bhishma and Drona, who are worthy of my worship?
5. It would be better to live in this world by begging than to live at the cost of the lives of great souls who are my teachers. Even though they are avaricious, they are superiors.
6. Nor do we know which is better — conquering them or being conquered by them. The sons of Dhritarashtra, whom if we killed we would not care to live, are now standing before us on the battlefield.
7. Now I am confused about my duty and have lost all composure because of weakness. In this condition I am asking You to tell me for certain what is best for me. Now I am Your disciple. Please instruct me.
8. I can find no means to drive away this grief which is drying up my senses. I will not be able to dispel it even if I win a prosperous, unrivalled kingdom on earth.
9. Sanjaya said: Having spoken thus, Arjuna, chastiser of enemies, told Krishna: I shall not fight, and fell silent.
10. O descendant of Bharata, at that time Krishna, smiling, in the midst of both armies, spoke the following words to the grief-stricken Arjuna.
11. The Supreme Personality of Godhead said: While speaking learned words, you are mourning for what is not worthy of grief. Those who are wise lament neither for the living nor the dead.
12. Never was there a time when I did not exist, nor you, nor all these kings; nor in the future shall any of us cease to be.
13. As the embodied soul continuously passes, in this body, from boyhood to youth to old age, the soul similarly passes into another body at death. A sober person is not bewildered by such a change.
14. O son of Kunti, the nonpermanent appearance of happiness and distress and their disappearance in due course are like the appearance and disappearance of winter and summer seasons. They arise from sense perception, O scion of Bharata, and one must learn to tolerate them without being disturbed."""),
        18: ("Chapter 18", """1. Arjuna said: O mighty-armed one, I wish to understand the purpose of renunciation and of the renounced order of life, O killer of the Keshi demon, O master of the senses.
2. The Supreme Personality of Godhead said: The giving up of activities that are based on material desire is what great learned men call the renounced order of life. And giving up the results of all activities is what the wise call renunciation.
3. Some learned men declare that all kinds of fruitive activities should be given up as faulty, yet other sages maintain that acts of sacrifice, charity and penance should never be abandoned.
4. O best of the Bharatas, now hear My judgment about renunciation. O tiger among men, renunciation is declared in the scriptures to be of three kinds.
5. Acts of sacrifice, charity and penance are not to be given up; they must be performed. Indeed, sacrifice, charity and penance purify even the great souls.
6. All these activities should be performed without attachment or any expectation of result. They should be performed as a matter of duty, O son of Pritha. That is My final opinion.
64. Because you are My very dear friend, I am speaking to you My supreme instruction, the most confidential knowledge of all. Hear this from Me, for it is for your benefit.
65. Always think of Me, become My devotee, worship Me and offer your homage unto Me. Thus you will come to Me without fail. I promise you this because you are My very dear friend.
66. Abandon all varieties of religion and just surrender unto Me. I shall deliver you from all sinful reactions. Do not fear."""),
    },
    Book.MAHABHARATA: {
        1: ("Adi Parva", """1. Once upon a time, the great sage Vyasa, the son of Satyavati, composed this great work. He taught it first to his son Suka, and then to others who were worthy.
2. The Mahabharata is the story of the Pandavas and the Kauravas, the sons of two brothers — Pandu and Dhritarashtra.
3. Pandu was the father of the five Pandavas: Yudhishthira, Bhima, Arjuna, Nakula and Sahadeva. Dhritarashtra was the father of the hundred Kauravas, of whom Duryodhana was the eldest.
4. From their union was born Arjuna, who would one day stand on the great battlefield of Kurukshetra and receive the divine teaching from Krishna that became the Bhagavad Gita.
5. When Arjuna was born, a divine voice spoke from the heavens: This child shall be equal to the greatest warriors in might. He shall spread the glory of his family. He shall perform great acts of heroism.
6. Arjuna grew up to be the greatest archer the world had ever seen. He wielded the mighty bow called Gandiva, given to him by the god of fire, Agni.
7. Bhima was the second Pandava, born to Kunti from the wind god Vayu. He was the strongest of all the Pandavas, capable of defeating a thousand elephants in single combat.
8. Yudhishthira was the eldest and most righteous of the Pandavas. He was so devoted to truth that the earth itself would rise to bear his footstep.
9. Draupadi, the daughter of King Drupada, became the wife of all five Pandavas after the great swayamvara where Arjuna alone could string the mighty bow and hit the rotating fish target.
10. The rivalry between the Pandavas and Kauravas began in childhood and grew until it resulted in the great war of Kurukshetra."""),
        3: ("Vana Parva", """1. After losing the dice game, the five Pandavas were forced into twelve years of forest exile and one year of living in disguise.
2. Yudhishthira, the eldest Pandava, accepted the exile with grace and said: A man must always honour his word, for it is his word that makes him who he is.
3. Bhima was filled with anger at the injustice but restrained himself at Yudhishthira's wise counsel for peace and patience.
4. Draupadi wept bitterly and asked: How can a righteous man like Yudhishthira suffer such injustice at the hands of evil and deceitful men?
5. During the exile, Arjuna went on a great journey to obtain divine weapons from the gods, including the powerful Pashupatastra from Lord Shiva himself.
6. Krishna visited the Pandavas in the forest and promised them that justice would prevail in the end and dharma would be restored.
7. The forest years were a time of great hardship, learning and spiritual growth for all five brothers and Draupadi."""),
        6: ("Bhishma Parva", """1. On the first day of the great battle at Kurukshetra, both armies stood arrayed against each other on the vast plain in their full glory.
2. Bhishma, the grandsire of the Kurus and the oldest and greatest warrior alive, was appointed commander of the Kaurava forces for the first ten days.
3. Arjuna stood between the two armies in his chariot, with the divine Krishna as his charioteer, holding the reins of the four white horses.
4. Seeing his own kinsmen arrayed against him — his grandfather Bhishma, his teacher Drona, his cousin Duryodhana — Arjuna was overcome with grief.
5. His bow Gandiva slipped from his hands and his limbs trembled. He said: O Krishna, I see no good in killing my own kinsmen in this battle.
6. It was at this moment, on the battlefield of Kurukshetra, that Lord Krishna began to speak the eternal wisdom that would become the Bhagavad Gita."""),
    },
    Book.RAMAYANA: {
        1: ("Bala Kanda", """1. There was once a great and righteous king named Dasharatha who ruled the prosperous kingdom of Ayodhya on the banks of the river Sarayu.
2. King Dasharatha had three queens — Kaushalya, Kaikeyi, and Sumitra — but no children, which caused him great sorrow.
3. After a great horse sacrifice, the gods were pleased and blessed the king. From the sacred fire emerged a divine being bearing a golden vessel of sacred pudding.
4. Kaushalya gave birth to the eldest son Rama, who was the very embodiment of dharma and virtue. All the people of Ayodhya rejoiced at his birth.
5. Kaikeyi gave birth to Bharata and Sumitra to the twins Lakshmana and Shatrughna. The four brothers loved each other dearly.
6. Rama was the most beloved of all the princes — his face shone like the full moon, his arms were long and strong, and his eyes were dark like the lotus flower.
7. The sage Vishwamitra came to King Dasharatha and asked that young Rama be sent with him to protect his sacrifice from the demons who disturbed it.
8. Rama and Lakshmana went with the sage and successfully destroyed the demoness Tataka and protected the sacrifice of Vishwamitra.
9. At the great swayamvara held by King Janaka, Rama alone was able to lift and string the mighty bow of Lord Shiva, winning the hand of the beautiful princess Sita.
10. Sita was the daughter of King Janaka, who had found her as a baby girl while plowing the earth for a sacred ritual, and she was raised as his own beloved daughter."""),
        5: ("Sundara Kanda", """1. Hanuman, the mighty son of the wind god Vayu and the most devoted servant of Rama, leaped across the vast ocean to reach the island kingdom of Lanka.
2. He searched through the entire golden city of Lanka, which was full of demons and warriors, until at last he found Sita sitting in the Ashoka grove.
3. Sita was surrounded by demoness guards and sat in great sorrow, thinking always of her beloved husband Rama and praying for his arrival.
4. Hanuman revealed himself to Sita and showed her the signet ring of Lord Rama as proof that he had been sent by her husband to find her.
5. Sita wept with joy when she saw the ring. She gave Hanuman her own jewel from her hair as a token for Rama, proof that she was alive and well.
6. Hanuman then allowed himself to be captured by Ravana's soldiers so that he could meet the demon king and warn him of the consequences of his actions.
7. Ravana, proud and arrogant, dismissed Hanuman's warnings. He ordered Hanuman's tail to be set on fire as an insult.
8. But Hanuman used his burning tail to set fire to the whole city of Lanka before escaping back across the ocean to report to Rama.
9. When Hanuman returned to Rama and delivered the jewel and the news that Sita was alive, Rama embraced him with great joy and gratitude."""),
        6: ("Yuddha Kanda", """1. With the help of the monkey king Sugriva and his great army, Rama prepared to cross the ocean and attack Lanka to rescue Sita.
2. The architect among the monkeys, Nala, built a great bridge across the ocean using rocks and boulders, and the army crossed over to Lanka.
3. Ravana's brother Vibhishana, who was righteous and refused to support his brother's wrongdoing, came to Rama and surrendered to him.
4. Rama accepted Vibhishana with open arms and made him an ally, showing that a righteous man is always welcome regardless of his birth.
5. The great battle of Lanka lasted many days. Many heroes fell on both sides and the earth was covered with the slain.
6. At last, Rama faced Ravana himself. The great demon had ten heads and twenty arms and was a mighty warrior who had conquered the three worlds.
7. Rama killed Ravana with the divine Brahmastra weapon given to him by the sage Agastya, and Sita was at last freed from her captivity."""),
    },
}


def create_sample_texts() -> None:
    """Write sample texts to data/sources/ for development."""
    logger.info("Creating sample texts for development...")

    # Bhagavad Gita
    gita_dir = SOURCES_DIR / "bhagavad_gita"
    gita_dir.mkdir(parents=True, exist_ok=True)
    gita_text = ""
    for sec_num, (sec_name, text) in SAMPLE_TEXTS[Book.BHAGAVAD_GITA].items():
        gita_text += f"\n\n=== {sec_name} ===\n\n{text}\n"
    (gita_dir / "gita.txt").write_text(gita_text.strip(), encoding="utf-8")
    logger.info("  ✓ Bhagavad Gita sample text created")

    # Mahabharata
    mbh_dir = SOURCES_DIR / "mahabharata"
    mbh_dir.mkdir(parents=True, exist_ok=True)
    for sec_num, (sec_name, text) in SAMPLE_TEXTS[Book.MAHABHARATA].items():
        fname = f"{sec_num:02d}_{sec_name.replace(' ', '_').lower()}.txt"
        (mbh_dir / fname).write_text(text, encoding="utf-8")
    logger.info("  ✓ Mahabharata sample texts created")

    # Ramayana
    ram_dir = SOURCES_DIR / "ramayana"
    ram_dir.mkdir(parents=True, exist_ok=True)
    for sec_num, (sec_name, text) in SAMPLE_TEXTS[Book.RAMAYANA].items():
        fname = f"{sec_num:02d}_{sec_name.replace(' ', '_').lower()}.txt"
        (ram_dir / fname).write_text(text, encoding="utf-8")
    logger.info("  ✓ Ramayana sample texts created")

    logger.info("  Sample texts ready in data/sources/")


def load_section_text(book: Book, section_number: int) -> str | None:
    """Load text for a specific book section."""
    source = SOURCE_FILES[book]

    # Single file (Bhagavad Gita)
    if source.is_file():
        return source.read_text(encoding="utf-8", errors="replace")

    # Directory (Mahabharata, Ramayana)
    if source.is_dir():
        section_map = get_section_map(book)
        section_name = section_map.get(section_number, "")
        candidates = [
            source / f"{section_number:02d}_{section_name.replace(' ', '_').lower()}.txt",
            source / f"{section_number:02d}.txt",
            source / f"section_{section_number}.txt",
        ]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8", errors="replace")

    return None


def ingest_book(
    book: Book,
    pipeline: EmbeddingPipeline,
    chunker: ShlokaChunker,
) -> int:
    """Ingest all available sections of a book."""
    section_map = get_section_map(book)
    total = 0

    for sec_num, sec_name in section_map.items():
        text = load_section_text(book, sec_num)
        if not text:
            continue

        logger.info(f"  Processing {sec_name} ({len(text):,} chars)...")
        chunks = chunker.chunk_book(text, book, sec_num, sec_name)
        logger.info(f"    → {len(chunks)} chunks generated")

        inserted = pipeline.upsert_chunks(chunks)
        total += inserted
        if inserted > 0:
            logger.info(f"    → {inserted} new chunks stored")

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="GyanaDev — Book Ingestion Pipeline")
    parser.add_argument("--samples", action="store_true", help="Create sample texts then ingest")
    parser.add_argument("--all", action="store_true", help="Ingest all books")
    parser.add_argument("--book", choices=["mahabharata", "ramayana", "bhagavad_gita"])
    parser.add_argument("--stats", action="store_true", help="Show corpus stats and exit")
    args = parser.parse_args()

    settings = get_settings()

    groq_client = GroqClient(
        api_key=settings.groq_api_key,
    )
    qdrant_store = QdrantStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection_name=settings.qdrant_collection,
    )

    if args.stats:
        stats = qdrant_store.get_stats()
        print(f"\n📊 GyanaDev Corpus Stats")
        print(f"   Collection : {stats['collection']}")
        print(f"   Total chunks: {stats['total_chunks']:,}")
        print(f"   Embed dim  : {stats['embed_dim']}")
        return

    if args.samples:
        create_sample_texts()

    pipeline = EmbeddingPipeline(
        groq_client=groq_client,
        qdrant_store=qdrant_store,
    )
    chunker = ShlokaChunker(target_tokens=400, overlap_verses=2)

    books_to_ingest: list[Book] = []
    if args.all or args.samples:
        books_to_ingest = list(Book)
    elif args.book:
        books_to_ingest = [Book(args.book)]
    else:
        parser.print_help()
        sys.exit(1)

    total = 0
    for book in books_to_ingest:
        logger.info(f"\n{'='*50}")
        logger.info(f"📖 Ingesting: {book.value.upper()}")
        logger.info(f"{'='*50}")
        inserted = ingest_book(book, pipeline, chunker)
        total += inserted
        logger.info(f"  ✓ {book.value}: {inserted} new chunks")

    stats = qdrant_store.get_stats()
    logger.info(f"\n🎉 Done! Total corpus: {stats['total_chunks']:,} chunks")


if __name__ == "__main__":
    main()